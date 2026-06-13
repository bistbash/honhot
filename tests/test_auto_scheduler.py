"""Tests for the pure auto-scheduling engine."""

from __future__ import annotations

from app.config import DAYS, HOURS
from app.services.auto_scheduler import (
    EntityCandidate,
    TutorState,
    plan_assignments,
)

ALL_CELLS = {(d, h) for d in range(len(DAYS)) for h in HOURS}
GRADE = 'י"א'


def _entity(
    i: int,
    subject_id: int,
    units: int,
    grade: str = GRADE,
    hours: int = 1,
    person_key: str | None = None,
    preferred_tutor_id: int | None = None,
) -> EntityCandidate:
    return EntityCandidate(
        entity_type="student",
        entity_id=i,
        subject_id=subject_id,
        grade=grade,
        units=units,
        label=f"student{i}",
        person_key=person_key or f"student{i}",
        required_hours=hours,
        preferred_tutor_id=preferred_tutor_id,
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
    entities = [
        _entity(1, subject_id=1, units=5, grade="י\"א"),
        _entity(2, subject_id=1, units=5, grade="י'"),
        _entity(3, subject_id=1, units=3, grade="י\"א"),
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
    assert len(cells) == 3


def test_multiple_hours_placed_in_consecutive_same_day_block() -> None:
    entities = [_entity(1, subject_id=1, units=5, hours=3)]
    tutors = [_tutor(1, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    days = [a.day for a in result.assignments]
    hours = sorted(a.hour for a in result.assignments)
    assert len(set(days)) == 1
    assert hours[-1] - hours[0] + 1 == 3


def test_cross_subject_same_person_forms_compact_day_block() -> None:
    person = "דני|י\"א|2"
    entities = [
        _entity(1, subject_id=1, units=5, hours=1, person_key=person),
        _entity(2, subject_id=2, units=5, hours=1, person_key=person),
    ]
    tutors = [_tutor(1, {(1, GRADE, 5), (2, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 2
    assert len({a.tutor_id for a in result.assignments}) == 1
    days = {a.day for a in result.assignments}
    assert len(days) == 1
    assigned_hours = sorted(a.hour for a in result.assignments)
    assert assigned_hours[1] - assigned_hours[0] == 1


def test_preferred_tutor_kept_when_filling_missing_hours() -> None:
    entities = [
        _entity(
            1,
            subject_id=1,
            units=5,
            hours=2,
            preferred_tutor_id=2,
        )
    ]
    tutors = [_tutor(1, {(1, GRADE, 5)}), _tutor(2, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 2
    assert all(a.tutor_id == 2 for a in result.assignments)


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
    entities = [_entity(1, subject_id=1, units=5, hours=3)]
    tutors = [_tutor(1, {(1, GRADE, 5)}), _tutor(2, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 3
    used_tutors = {a.tutor_id for a in result.assignments}
    assert len(used_tutors) == 1


def test_two_entities_balanced_across_two_tutors_with_continuity() -> None:
    entities = [
        _entity(1, subject_id=1, units=5, hours=3),
        _entity(2, subject_id=1, units=5, hours=3),
    ]
    tutors = [_tutor(1, {(1, GRADE, 5)}), _tutor(2, {(1, GRADE, 5)})]
    result = plan_assignments(entities, tutors, {})
    assert result.assigned_count == 6
    assert tutors[0].load == 3
    assert tutors[1].load == 3
