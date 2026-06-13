"""Automatic, load-balanced assignment engine.

Pure business logic (no Qt, no DB). Given the schedulable entities (each needing
a number of weekly hours), the available tutors and the subjects' reserved
windows, it produces a plan that assigns the required hours to qualified,
available tutor slots while keeping the per-tutor workload balanced.

Heuristic
---------
1. Process entities grouped by person (same student across subjects), most-
   constrained first within each person, so hard-to-place entities get first pick.
2. **Continuity** - try to give all of an entity's weekly hours to a single
   tutor (preferring the tutor already teaching that person or entity).
3. **Person comfort** - when the same person already has lessons on a day,
   extend that day's block to minimise gaps between their subjects.
4. **Tutor comfort** - spread a tutor's hours across the week and avoid long
   consecutive teaching streaks (soft limit, see ``TUTOR_PREFERRED_MAX_CONSECUTIVE``).
5. **Balance** - when continuity is impossible, fill hour-by-hour, always
   choosing the least-loaded qualified tutor, which greedily minimises the
   maximum tutor load and yields a near-even spread of teaching hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import TUTOR_PREFERRED_MAX_CONSECUTIVE


@dataclass(frozen=True)
class EntityCandidate:
    """An entity that needs to be scheduled for a number of weekly hours."""

    entity_type: str  # "student" | "group"
    entity_id: int
    subject_id: int
    grade: str
    units: int
    label: str
    person_key: str
    required_hours: int = 1
    preferred_tutor_id: int | None = None


@dataclass
class TutorState:
    """A tutor's qualifications and the cells they can still teach in."""

    tutor_id: int
    name: str
    # Set of (subject_id, grade, units) the tutor is qualified to teach.
    qualifications: set[tuple[int, str, int]]
    # (day, hour) cells the tutor is available and not yet occupied.
    free_cells: set[tuple[int, int]]
    # (day, hour) cells already assigned to this tutor.
    occupied_cells: set[tuple[int, int]] = field(default_factory=set)
    load: int = 0

    def can_teach(self, entity: "EntityCandidate") -> bool:
        return (entity.subject_id, entity.grade, entity.units) in self.qualifications


@dataclass(frozen=True)
class PlannedAssignment:
    """A single proposed assignment of one hour."""

    entity_type: str
    entity_id: int
    subject_id: int
    tutor_id: int
    day: int
    hour: int


@dataclass
class Shortfall:
    """An entity that could not be fully scheduled."""

    entity: EntityCandidate
    missing_hours: int


@dataclass
class AutoScheduleResult:
    """The outcome of a planning run."""

    assignments: list[PlannedAssignment] = field(default_factory=list)
    shortfalls: list[Shortfall] = field(default_factory=list)

    @property
    def assigned_count(self) -> int:
        return len(self.assignments)

    @property
    def shortfall_count(self) -> int:
        return len(self.shortfalls)


def _gap_count(hours: set[int]) -> int:
    """Return the number of empty hours between lessons on the same day."""
    if len(hours) <= 1:
        return 0
    sorted_hours = sorted(hours)
    return sum(
        sorted_hours[i + 1] - sorted_hours[i] - 1
        for i in range(len(sorted_hours) - 1)
    )


def _person_day_hours(
    person_occupied: set[tuple[int, int]], day: int
) -> set[int]:
    return {hour for d, hour in person_occupied if d == day}


def _tutor_day_hours(occupied: set[tuple[int, int]], day: int) -> int:
    return sum(1 for d, _ in occupied if d == day)


def _tutor_distinct_days(occupied: set[tuple[int, int]]) -> int:
    return len({d for d, _ in occupied})


def _tutor_consecutive_streak(
    occupied: set[tuple[int, int]], day: int, hour: int
) -> int:
    """Return consecutive teaching streak on ``day`` after adding ``hour``."""
    hours_on_day = {h for d, h in occupied if d == day} | {hour}
    sorted_hours = sorted(hours_on_day)
    runs: list[list[int]] = []
    current = [sorted_hours[0]]
    for h in sorted_hours[1:]:
        if h - current[-1] == 1:
            current.append(h)
        else:
            runs.append(current)
            current = [h]
    runs.append(current)
    for run in runs:
        if hour in run:
            return len(run)
    return 1


def _tutor_streak_penalty(streak: int, preferred_max: int) -> int:
    if streak <= preferred_max:
        return 0
    return streak - preferred_max


def _cell_score(
    day: int,
    hour: int,
    person_occupied: set[tuple[int, int]],
    person_baseline: set[tuple[int, int]],
    tutor_occupied: set[tuple[int, int]],
    preferred_max_consecutive: int,
) -> tuple[int, int, int, int, int, int, int]:
    """Lexicographic score for picking a cell (lower is better)."""
    baseline_on_day = _person_day_hours(person_baseline, day)
    tutor_day_count = _tutor_day_hours(tutor_occupied, day)

    # Only honour person day-continuity from hours scheduled before this entity.
    person_has_day = 0 if baseline_on_day else 1
    combined = baseline_on_day | {hour}
    person_gaps = _gap_count(combined) if baseline_on_day else 0

    streak = _tutor_consecutive_streak(tutor_occupied, day, hour)
    streak_penalty = _tutor_streak_penalty(streak, preferred_max_consecutive)
    tutor_new_day = 0 if tutor_day_count == 0 else 1

    return (
        person_has_day,
        person_gaps,
        tutor_day_count,
        streak_penalty,
        tutor_new_day,
        day,
        hour,
    )


def _select_cells_scored(
    feasible: set[tuple[int, int]],
    count: int,
    person_occupied: set[tuple[int, int]],
    person_baseline: set[tuple[int, int]],
    tutor_occupied: set[tuple[int, int]],
    used_cells: set[tuple[int, int]],
    preferred_max_consecutive: int = TUTOR_PREFERRED_MAX_CONSECUTIVE,
) -> list[tuple[int, int]]:
    """Pick up to ``count`` cells, balancing person and tutor comfort."""
    if count <= 0:
        return []

    available = feasible - used_cells
    if not available:
        return []

    chosen: list[tuple[int, int]] = []
    local_tutor = set(tutor_occupied)
    remaining = count

    while remaining > 0:
        pool = sorted(available)
        if not pool:
            break

        best_cell: tuple[int, int] | None = None
        best_score: tuple | None = None

        for day, hour in pool:
            score = _cell_score(
                day,
                hour,
                person_occupied,
                person_baseline,
                local_tutor,
                preferred_max_consecutive,
            )
            if best_score is None or score < best_score:
                best_score = score
                best_cell = (day, hour)

        if best_cell is None:
            break

        chosen.append(best_cell)
        available.discard(best_cell)
        local_tutor.add(best_cell)
        remaining -= 1

    return chosen


def _tutor_sort_key(
    tutor: TutorState,
    preferred_tutor_id: int | None,
    person_tutor_id: int | None,
) -> tuple:
    return (
        tutor.tutor_id != preferred_tutor_id if preferred_tutor_id else False,
        tutor.tutor_id != person_tutor_id if person_tutor_id else False,
        tutor.load,
        tutor.name,
        tutor.tutor_id,
    )


def _phase2_pick(
    candidates: list[TutorState],
    feasible_for,
    person_cells: set[tuple[int, int]],
    person_baseline: set[tuple[int, int]],
    used_cells: set[tuple[int, int]],
    preferred_tutor_id: int | None,
    person_tutor_id: int | None,
) -> tuple[TutorState, tuple[int, int]] | None:
    """Choose the best (tutor, cell) pair for one hour of Phase-2 fill."""
    best_key: tuple | None = None
    best_tutor: TutorState | None = None
    best_cell: tuple[int, int] | None = None

    for tutor in candidates:
        cells = _select_cells_scored(
            feasible_for(tutor),
            1,
            person_cells,
            person_baseline,
            tutor.occupied_cells,
            used_cells,
        )
        if not cells:
            continue
        cell = cells[0]
        day, hour = cell
        key = (
            *_tutor_sort_key(tutor, preferred_tutor_id, person_tutor_id)[:2],
            tutor.load,
            *_cell_score(
                day,
                hour,
                person_cells,
                person_baseline,
                tutor.occupied_cells,
                TUTOR_PREFERRED_MAX_CONSECUTIVE,
            ),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_tutor = tutor
            best_cell = cell

    if best_tutor is None or best_cell is None:
        return None
    return best_tutor, best_cell


def plan_assignments(
    entities: list[EntityCandidate],
    tutors: list[TutorState],
    subject_windows: dict[int, set[tuple[int, int]]],
    person_occupied: dict[str, set[tuple[int, int]]] | None = None,
    person_tutor: dict[str, int] | None = None,
) -> AutoScheduleResult:
    """Compute a balanced assignment plan.

    Args:
        entities: entities to schedule, each with ``required_hours``.
        tutors: candidate tutors with qualifications and free cells. These
            objects are mutated (``free_cells`` shrink, ``load`` grows) so the
            caller should pass throwaway copies.
        subject_windows: ``{subject_id: {(day, hour), ...}}``. A subject absent
            from the mapping (or mapped to an empty set) is unrestricted.
        person_occupied: existing and planned cells per person key, mutated in
            place as assignments are committed.
        person_tutor: preferred tutor per person key, updated after each commit.

    Returns:
        An :class:`AutoScheduleResult` with the planned assignments and any
        entities that could not be fully scheduled.
    """
    if person_occupied is None:
        person_occupied = {}
    if person_tutor is None:
        person_tutor = {}

    result = AutoScheduleResult()

    qualified: dict[int, list[TutorState]] = {
        i: [t for t in tutors if t.can_teach(entity)]
        for i, entity in enumerate(entities)
    }

    order = sorted(
        range(len(entities)),
        key=lambda i: (
            entities[i].person_key,
            len(qualified[i]),
            -entities[i].required_hours,
            entities[i].label,
            entities[i].entity_id,
        ),
    )

    for index in order:
        entity = entities[index]
        candidates = qualified[index]
        allowed = subject_windows.get(entity.subject_id) or None
        used_cells: set[tuple[int, int]] = set()
        remaining = entity.required_hours
        person_cells = person_occupied.setdefault(entity.person_key, set())
        person_baseline = set(person_cells)
        person_tutor_id = person_tutor.get(entity.person_key)

        def feasible_for(tutor: TutorState) -> set[tuple[int, int]]:
            cells = tutor.free_cells - used_cells - person_cells
            return cells & allowed if allowed is not None else cells

        def commit(tutor: TutorState, cell: tuple[int, int]) -> None:
            tutor.free_cells.discard(cell)
            tutor.occupied_cells.add(cell)
            tutor.load += 1
            used_cells.add(cell)
            person_cells.add(cell)
            person_tutor[entity.person_key] = tutor.tutor_id
            result.assignments.append(
                PlannedAssignment(
                    entity_type=entity.entity_type,
                    entity_id=entity.entity_id,
                    subject_id=entity.subject_id,
                    tutor_id=tutor.tutor_id,
                    day=cell[0],
                    hour=cell[1],
                )
            )

        # Phase 1: continuity - preferred tutor that fits ALL the hours.
        for tutor in sorted(
            candidates,
            key=lambda t: _tutor_sort_key(
                t, entity.preferred_tutor_id, person_tutor_id
            ),
        ):
            cells = _select_cells_scored(
                feasible_for(tutor),
                remaining,
                person_cells,
                person_baseline,
                tutor.occupied_cells,
                used_cells,
            )
            if len(cells) == remaining:
                for cell in cells:
                    commit(tutor, cell)
                remaining = 0
                break

        # Phase 2: balanced fill across tutors, one hour at a time.
        while remaining > 0:
            pick = _phase2_pick(
                candidates,
                feasible_for,
                person_cells,
                person_baseline,
                used_cells,
                entity.preferred_tutor_id,
                person_tutor.get(entity.person_key),
            )
            if pick is None:
                break
            best_tutor, best_cell = pick
            commit(best_tutor, best_cell)
            remaining -= 1

        if remaining > 0:
            result.shortfalls.append(
                Shortfall(entity=entity, missing_hours=remaining)
            )

    return result
