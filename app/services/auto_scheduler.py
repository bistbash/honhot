"""Automatic, load-balanced assignment engine.

Pure business logic (no Qt, no DB). Given the schedulable entities (each needing
a number of weekly hours), the available tutors and the subjects' reserved
windows, it produces a plan that assigns the required hours to qualified,
available tutor slots while keeping the per-tutor workload balanced.

Heuristic
---------
1. Process the most-constrained entities first (fewest qualified tutors, then
   most required hours), so hard-to-place entities get first pick.
2. **Continuity** - try to give all of an entity's weekly hours to a single
   tutor (the least-loaded qualified one that can fit them all). Keeping a
   student with one tutor is pedagogically preferable.
3. **Day spreading** - an entity's multiple weekly hours are placed on distinct
   days when possible, rather than stacked on one day.
4. **Balance** - when continuity is impossible, fill hour-by-hour, always
   choosing the least-loaded qualified tutor, which greedily minimises the
   maximum tutor load and yields a near-even spread of teaching hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntityCandidate:
    """An entity that needs to be scheduled for a number of weekly hours."""

    entity_type: str  # "student" | "group"
    entity_id: int
    subject_id: int
    grade: str
    units: int
    label: str
    required_hours: int = 1


@dataclass
class TutorState:
    """A tutor's qualifications and the cells they can still teach in."""

    tutor_id: int
    name: str
    # Set of (subject_id, grade, units) the tutor is qualified to teach.
    qualifications: set[tuple[int, str, int]]
    # (day, hour) cells the tutor is available and not yet occupied.
    free_cells: set[tuple[int, int]]
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


def _select_cells(
    feasible: set[tuple[int, int]],
    count: int,
    used_days: set[int],
) -> list[tuple[int, int]]:
    """Pick up to ``count`` cells, preferring new days, then earliest slots."""
    chosen: list[tuple[int, int]] = []
    local_days = set(used_days)
    pool = sorted(feasible)  # deterministic: (day, hour) ascending
    while len(chosen) < count and pool:
        pick = next((c for c in pool if c[0] not in local_days), pool[0])
        chosen.append(pick)
        local_days.add(pick[0])
        pool.remove(pick)
    return chosen


def plan_assignments(
    entities: list[EntityCandidate],
    tutors: list[TutorState],
    subject_windows: dict[int, set[tuple[int, int]]],
) -> AutoScheduleResult:
    """Compute a balanced assignment plan.

    Args:
        entities: entities to schedule, each with ``required_hours``.
        tutors: candidate tutors with qualifications and free cells. These
            objects are mutated (``free_cells`` shrink, ``load`` grows) so the
            caller should pass throwaway copies.
        subject_windows: ``{subject_id: {(day, hour), ...}}``. A subject absent
            from the mapping (or mapped to an empty set) is unrestricted.

    Returns:
        An :class:`AutoScheduleResult` with the planned assignments and any
        entities that could not be fully scheduled.
    """
    result = AutoScheduleResult()

    qualified: dict[int, list[TutorState]] = {
        i: [t for t in tutors if t.can_teach(entity)]
        for i, entity in enumerate(entities)
    }

    # Most-constrained entities first; deterministic tie-breaks.
    order = sorted(
        range(len(entities)),
        key=lambda i: (
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
        used_days: set[int] = set()
        remaining = entity.required_hours

        def feasible_for(tutor: TutorState) -> set[tuple[int, int]]:
            cells = tutor.free_cells - used_cells
            return cells & allowed if allowed is not None else cells

        def commit(tutor: TutorState, cell: tuple[int, int]) -> None:
            tutor.free_cells.discard(cell)
            tutor.load += 1
            used_cells.add(cell)
            used_days.add(cell[0])
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

        # Phase 1: continuity - least-loaded tutor that fits ALL the hours.
        for tutor in sorted(
            candidates, key=lambda t: (t.load, t.name, t.tutor_id)
        ):
            cells = _select_cells(feasible_for(tutor), remaining, used_days)
            if len(cells) == remaining:
                for cell in cells:
                    commit(tutor, cell)
                remaining = 0
                break

        # Phase 2: balanced fill across tutors, one hour at a time.
        while remaining > 0:
            best_tutor: TutorState | None = None
            best_cell: tuple[int, int] | None = None
            for tutor in sorted(
                candidates,
                key=lambda t: (t.load, len(t.free_cells), t.name, t.tutor_id),
            ):
                cells = _select_cells(feasible_for(tutor), 1, used_days)
                if cells:
                    best_tutor, best_cell = tutor, cells[0]
                    break
            if best_tutor is None or best_cell is None:
                break
            commit(best_tutor, best_cell)
            remaining -= 1

        if remaining > 0:
            result.shortfalls.append(
                Shortfall(entity=entity, missing_hours=remaining)
            )

    return result
