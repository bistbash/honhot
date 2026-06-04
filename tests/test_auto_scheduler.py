"""Tests for the pure auto-scheduling engine."""

from __future__ import annotations

from app.config import DAYS, HOURS
from app.services.auto_scheduler import (
    EntityCandidate,
    TutorState,
    plan_assignments,
)

ALL_CELLS = {(d, h) for d in range(len(DAYS)) for h in HOURS}
GRADE = "י\"א"


def _entity(
    i: int, subject_id: int, units: int, grade: str = GRADE, hours: int = 1
) -> EntityCandidate:
    return EntityCandidate(
        entity_type="student",
        entity_id=i,
        subject_id=subject_id,
        grade=grade,
        units=units,
        label=f"student{i}",
        required_hours=hours,
    )


def _tutor(
    tid: int, quals: set[tuple[int, str, int]], free=None
) -> TutorState:
    return TutorState(
        tutor_id=tid,
        name=f"tutor{tid}",
        qualifications=quals,
        free_cells=set(ALL_CELLS if free is None else free),
    )


def test_balances_load_across_two_tutors() -> None:
    entities = [_entity(i, subject_id=1, units=5) for i in range(10)]
    tutors = [_tutor(1, {(1, GRADE, 5)}), _tutor(2, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 10
    assert not result.shortfalls
    assert tutors[0].load == 5
    assert tutors[1].load == 5


def test_respects_grade_and_units_qualification() -> None:
    # Tutor qualified for grade י"א units 5 only.
    entities = [
        _entity(1, subject_id=1, units=5, grade="י\"א"),
        _entity(2, subject_id=1, units=5, grade="י'"),  # wrong grade
        _entity(3, subject_id=1, units=3, grade="י\"א"),  # wrong units
    ]
    tutors = [_tutor(1, {(1, "י\"א", 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 1
    assert result.assignments[0].entity_id == 1
    assert result.shortfall_count == 2


def test_multiple_weekly_hours_assigned_distinct_cells() -> None:
    entities = [_entity(1, subject_id=1, units=5, hours=3)]
    tutors = [_tutor(1, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 3
    cells = {(a.day, a.hour) for a in result.assignments}
    assert len(cells) == 3  # no repeated (day, hour)


def test_respects_subject_windows() -> None:
    entities = [_entity(1, subject_id=1, units=5)]
    tutors = [_tutor(1, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {1: {(2, 3)}})
    assert result.assigned_count == 1
    assert (result.assignments[0].day, result.assignments[0].hour) == (2, 3)


def test_shortfall_when_capacity_insufficient() -> None:
    entities = [_entity(1, subject_id=1, units=5, hours=3)]
    tutors = [_tutor(1, {(1, GRADE, 5)}, free={(0, 0), (1, 1)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 2
    assert result.shortfall_count == 1
    assert result.shortfalls[0].missing_hours == 1


def test_continuity_keeps_entity_with_one_tutor() -> None:
    """An entity's weekly hours should stay with a single tutor when possible."""
    entities = [_entity(1, subject_id=1, units=5, hours=3)]
    tutors = [_tutor(1, {(1, GRADE, 5)}), _tutor(2, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 3
    used_tutors = {a.tutor_id for a in result.assignments}
    assert len(used_tutors) == 1  # all three hours with the same tutor


def test_multiple_hours_spread_across_distinct_days() -> None:
    entities = [_entity(1, subject_id=1, units=5, hours=3)]
    tutors = [_tutor(1, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    days = [a.day for a in result.assignments]
    assert len(set(days)) == 3  # one per distinct day


def test_two_entities_balanced_across_two_tutors_with_continuity() -> None:
    entities = [
        _entity(1, subject_id=1, units=5, hours=3),
        _entity(2, subject_id=1, units=5, hours=3),
    ]
    tutors = [_tutor(1, {(1, GRADE, 5)}), _tutor(2, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 6
    # Each tutor takes exactly one entity (3 hours): balanced + continuous.
    assert tutors[0].load == 3
    assert tutors[1].load == 3
