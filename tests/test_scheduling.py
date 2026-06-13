"""Tests for schedule assignment validation (the core business rules)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.controllers.schedule_controller import ScheduleController
from app.controllers.subject_controller import SubjectController
from app.controllers.tutor_controller import TutorController
from app.database import session_scope
from app.models import EntityType, ScheduleSlot, Student, Subject, Tutor
from tests.student_ids import ID_DANI, ID_GENERIC, ID_IDAN, ID_RON

GRADE = 'י"א'


@pytest.fixture
def seeded():
    """Create one subject (1 weekly hour), two students and one tutor."""
    with session_scope() as session:
        subject = Subject(name="מתמטיקה", weekly_hours=1)
        session.add(subject)
        session.flush()

        s1 = Student(
            name="דני", national_id=ID_DANI, grade=GRADE, class_number=2, units=5, study_level=4,
            subject_id=subject.id,
        )
        s2 = Student(
            name="רותם", national_id=ID_RON, grade=GRADE, class_number=2, units=5, study_level=4,
            subject_id=subject.id,
        )
        tutor = Tutor(name="מאיה")
        session.add_all([s1, s2, tutor])
        session.flush()
        ids = {
            "subject": subject.id,
            "s1": s1.id,
            "s2": s2.id,
            "active": tutor.id,
        }
    # Qualify the tutor for math, grade י"א, units 5.
    TutorController().add_tutor_subject(
        ids["active"], ids["subject"], [GRADE], units_min=5, units_max=5
    )
    return ids


def test_student_person_key_uses_national_id(seeded) -> None:
    from app.controllers.schedule_controller import ScheduleController
    from app.database import session_scope

    with session_scope() as session:
        student = session.get(Student, seeded["s1"])
        assert student is not None
        assert ScheduleController._student_person_key(student) == student.national_id


def test_basic_assignment_succeeds(seeded) -> None:
    ctrl = ScheduleController()
    res = ctrl.try_assign(
        seeded["active"], 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert res.ok
    assert (2, 3) in ctrl.slots_for_tutor(seeded["active"])


def test_reject_occupied_slot(seeded) -> None:
    ctrl = ScheduleController()
    ctrl.try_assign(seeded["active"], 1, 4, EntityType.STUDENT.value, seeded["s1"])
    res = ctrl.try_assign(
        seeded["active"], 1, 4, EntityType.STUDENT.value, seeded["s2"]
    )
    assert not res.ok
    assert "תפוסה" in res.message


def test_reject_entity_time_conflict(seeded) -> None:
    """Same student cannot sit with two tutors at the same day+hour."""
    with session_scope() as session:
        another = Tutor(name="שרה")
        session.add(another)
        session.flush()
        other_id = another.id

    TutorController().add_tutor_subject(
        other_id, seeded["subject"], [GRADE], units_min=5, units_max=5
    )
    ctrl = ScheduleController()
    ctrl.try_assign(seeded["active"], 0, 5, EntityType.STUDENT.value, seeded["s1"])
    res = ctrl.try_assign(other_id, 0, 5, EntityType.STUDENT.value, seeded["s1"])
    assert not res.ok
    assert "כבר משובצת" in res.message


def test_reject_outside_reserved_window(seeded) -> None:
    """A reserved subject can only be scheduled in its windows."""
    SubjectController().set_windows(seeded["subject"], {(2, 3)})  # Tuesday hour 3
    ctrl = ScheduleController()

    blocked = ctrl.try_assign(
        seeded["active"], 1, 6, EntityType.STUDENT.value, seeded["s1"]
    )
    assert not blocked.ok
    assert "משוריין" in blocked.message

    allowed = ctrl.try_assign(
        seeded["active"], 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert allowed.ok


def test_unassign_frees_slot(seeded) -> None:
    ctrl = ScheduleController()
    ctrl.try_assign(seeded["active"], 3, 2, EntityType.STUDENT.value, seeded["s1"])
    ctrl.unassign(seeded["active"], 3, 2)
    assert (3, 2) not in ctrl.slots_for_tutor(seeded["active"])


def test_move_assignment_relocates_lesson(seeded) -> None:
    ctrl = ScheduleController()
    ctrl.try_assign(seeded["active"], 2, 3, EntityType.STUDENT.value, seeded["s1"])
    result = ctrl.move_assignment(seeded["active"], 2, 3, 2, 4)
    assert result.ok
    slots = ctrl.slots_for_tutor(seeded["active"])
    assert (2, 3) not in slots
    assert (2, 4) in slots


def test_move_assignment_rejected_restores_source(seeded) -> None:
    TutorController().set_unavailability(seeded["active"], {(2, 5)})
    ctrl = ScheduleController()
    ctrl.try_assign(seeded["active"], 2, 3, EntityType.STUDENT.value, seeded["s1"])
    result = ctrl.move_assignment(seeded["active"], 2, 3, 2, 5)
    assert not result.ok
    slots = ctrl.slots_for_tutor(seeded["active"])
    assert (2, 3) in slots  # original lesson restored
    assert (2, 5) not in slots


def test_reject_tutor_without_subject_qualification(seeded) -> None:
    with session_scope() as session:
        tutor = Tutor(name="ללא מקצוע")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id

    res = ScheduleController().try_assign(
        tutor_id, 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert not res.ok
    assert "לא מוגדרת" in res.message


def test_reject_wrong_grade_qualification(seeded) -> None:
    # Tutor qualified for a different grade only.
    with session_scope() as session:
        tutor = Tutor(name="שכבה אחרת")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id
    TutorController().add_tutor_subject(
        tutor_id, seeded["subject"], ["י'"], units_min=5, units_max=5
    )
    res = ScheduleController().try_assign(
        tutor_id, 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert not res.ok
    assert "שכבה" in res.message


def test_reject_wrong_units_qualification(seeded) -> None:
    with session_scope() as session:
        tutor = Tutor(name="יחל אחר")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id
    TutorController().add_tutor_subject(
        tutor_id, seeded["subject"], [GRADE], units_min=3, units_max=4
    )
    res = ScheduleController().try_assign(
        tutor_id, 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert not res.ok
    assert "5 יח\"ל" in res.message


def test_grade_range_qualification_matches(seeded) -> None:
    """A units range covering 5 and the correct grade should match."""
    with session_scope() as session:
        tutor = Tutor(name="טווח")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id
    TutorController().add_tutor_subject(
        tutor_id, seeded["subject"], [GRADE], units_min=3, units_max=5
    )
    res = ScheduleController().try_assign(
        tutor_id, 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert res.ok


def test_reject_tutor_unavailable_cell(seeded) -> None:
    TutorController().set_unavailability(seeded["active"], {(2, 1)})
    ctrl = ScheduleController()
    res = ctrl.try_assign(
        seeded["active"], 2, 1, EntityType.STUDENT.value, seeded["s1"]
    )
    assert not res.ok
    assert "אינה זמינה" in res.message
    ok = ctrl.try_assign(
        seeded["active"], 2, 2, EntityType.STUDENT.value, seeded["s1"]
    )
    assert ok.ok


def test_auto_assign_balances_and_respects_constraints(seeded) -> None:
    tutor_ctrl = TutorController()
    with session_scope() as session:
        other = Tutor(name="שרה")
        session.add(other)
        session.flush()
        other_id = other.id
    tutor_ctrl.add_tutor_subject(
        other_id, seeded["subject"], [GRADE], units_min=5, units_max=5
    )
    tutor_ctrl.set_unavailability(seeded["active"], {(0, 0)})

    summary = ScheduleController().auto_assign(clear_existing=True)

    # Two students (1 hour each), two qualified tutors -> one each.
    assert summary.assigned == 2
    assert not summary.unassigned_labels
    loads = dict(summary.tutor_loads)
    assert loads["מאיה"] == 1
    assert loads["שרה"] == 1

    with session_scope() as session:
        for slot in session.scalars(select(ScheduleSlot)).all():
            if slot.tutor_id == seeded["active"]:
                assert (slot.day, slot.hour) != (0, 0)


def test_auto_assign_multiple_weekly_hours(seeded) -> None:
    """A subject needing 3 weekly hours yields 3 slots per student."""
    SubjectController().set_weekly_hours(seeded["subject"], 3)
    summary = ScheduleController().auto_assign(clear_existing=True)
    # 2 students x 3 hours = 6 assignments, all to the single qualified tutor.
    assert summary.assigned == 6
    assert dict(summary.tutor_loads)["מאיה"] == 6

    ctrl = ScheduleController()
    entities = {e.entity_id: e for e in ctrl.schedulable_entities()}
    assert entities[seeded["s1"]].scheduled_count == 3
    assert entities[seeded["s1"]].required_hours == 3


def test_auto_assign_fill_only_missing_hours(seeded) -> None:
    SubjectController().set_weekly_hours(seeded["subject"], 2)
    ctrl = ScheduleController()
    # Manually place one hour for s1, then fill the rest.
    ctrl.try_assign(seeded["active"], 0, 0, EntityType.STUDENT.value, seeded["s1"])
    summary = ctrl.auto_assign(clear_existing=False)
    # s1 needs 1 more, s2 needs 2 -> 3 new assignments.
    assert summary.assigned == 3


def test_reject_global_blocked_cell(seeded) -> None:
    TutorController().set_global_unavailability({(2, 3)})
    ctrl = ScheduleController()
    res = ctrl.try_assign(
        seeded["active"], 2, 3, EntityType.STUDENT.value, seeded["s1"]
    )
    assert not res.ok
    assert "כללי" in res.message
    # A non-blocked cell still works.
    ok = ctrl.try_assign(
        seeded["active"], 2, 4, EntityType.STUDENT.value, seeded["s1"]
    )
    assert ok.ok


def test_auto_assign_avoids_global_blocked_cells(seeded) -> None:
    # Block an entire column-ish set of early cells for everyone.
    blocked = {(d, h) for d in range(6) for h in (0, 1)}
    TutorController().set_global_unavailability(blocked)
    ScheduleController().auto_assign(clear_existing=True)
    with session_scope() as session:
        for slot in session.scalars(select(ScheduleSlot)).all():
            assert (slot.day, slot.hour) not in blocked


def test_auto_assign_reports_unassigned_without_qualified_tutor() -> None:
    with session_scope() as session:
        subject = Subject(name="היסטוריה", weekly_hours=1)
        session.add(subject)
        session.flush()
        student = Student(
            name="עידן", national_id=ID_IDAN, grade="י'", class_number=1, units=4, study_level=3,
            subject_id=subject.id,
        )
        tutor = Tutor(name="ללא הסמכה")
        session.add_all([student, tutor])

    summary = ScheduleController().auto_assign(clear_existing=True)
    assert summary.assigned == 0
    assert "עידן" in " ".join(summary.unassigned_labels)


def test_auto_assign_skips_subject_without_weekly_hours(seeded) -> None:
    SubjectController().set_weekly_hours(seeded["subject"], None)
    summary = ScheduleController().auto_assign(clear_existing=True)
    assert summary.assigned == 0
    assert not summary.unassigned_labels


def test_auto_assign_honors_student_preferred_tutor(seeded) -> None:
    with session_scope() as session:
        preferred = Tutor(name="מועדפת")
        session.add(preferred)
        session.flush()
        preferred_id = preferred.id
        student = session.get(Student, seeded["s1"])
        assert student is not None
        student.preferred_tutor_id = preferred_id

    TutorController().add_tutor_subject(
        preferred_id, seeded["subject"], [GRADE], units_min=5, units_max=5
    )

    ScheduleController().auto_assign(clear_existing=True)

    with session_scope() as session:
        slots = session.scalars(
            select(ScheduleSlot).where(ScheduleSlot.student_id == seeded["s1"])
        ).all()
        assert len(slots) == 1
        assert slots[0].tutor_id == preferred_id


def test_auto_assign_honors_group_preferred_tutor(seeded) -> None:
    from app.models import StudyGroup

    with session_scope() as session:
        preferred = Tutor(name="לקבוצה")
        session.add(preferred)
        session.flush()
        preferred_id = preferred.id

        group = StudyGroup(
            name="קבוצת בדיקה",
            grade=GRADE,
            units=5,
            study_level=4,
            subject_id=seeded["subject"],
            preferred_tutor_id=preferred_id,
        )
        session.add(group)
        session.flush()
        for sid in (seeded["s1"], seeded["s2"]):
            student = session.get(Student, sid)
            assert student is not None
            student.study_group_id = group.id
        group_id = group.id

    TutorController().add_tutor_subject(
        preferred_id, seeded["subject"], [GRADE], units_min=5, units_max=5
    )

    ScheduleController().auto_assign(clear_existing=True)

    with session_scope() as session:
        slots = session.scalars(
            select(ScheduleSlot).where(ScheduleSlot.study_group_id == group_id)
        ).all()
        assert len(slots) == 1
        assert slots[0].tutor_id == preferred_id


def test_explicit_preferred_tutor_overrides_existing_slots(seeded) -> None:
    """DB preference wins over tutor inferred from existing assignments."""
    with session_scope() as session:
        other = Tutor(name="אחרת")
        session.add(other)
        session.flush()
        other_id = other.id
        student = session.get(Student, seeded["s1"])
        assert student is not None
        student.preferred_tutor_id = other_id

    TutorController().add_tutor_subject(
        other_id, seeded["subject"], [GRADE], units_min=5, units_max=5
    )

    ctrl = ScheduleController()
    ctrl.try_assign(seeded["active"], 0, 0, EntityType.STUDENT.value, seeded["s1"])
    SubjectController().set_weekly_hours(seeded["subject"], 2)
    ctrl.auto_assign(clear_existing=False)

    with session_scope() as session:
        slots = sorted(
            session.scalars(
                select(ScheduleSlot).where(ScheduleSlot.student_id == seeded["s1"])
            ).all(),
            key=lambda s: (s.day, s.hour),
        )
        assert len(slots) == 2
        assert slots[0].tutor_id == seeded["active"]
        assert slots[1].tutor_id == other_id


def test_schedulable_entities_marks_unqualified_for_tutor(seeded) -> None:
    from app.controllers.subject_controller import SubjectController

    physics_id = SubjectController().add_subject("פיזיקה")
    with session_scope() as session:
        physics_student = Student(
            name="פיזיקאי",
            national_id=ID_GENERIC,
            grade=GRADE,
            class_number=1,
            units=5,
            study_level=4,
            subject_id=physics_id,
        )
        session.add(physics_student)
        session.flush()
        physics_student_id = physics_student.id

    ctrl = ScheduleController()
    entities = {e.entity_id: e for e in ctrl.schedulable_entities()}
    math_entity = entities[seeded["s1"]]
    assert math_entity.assignable is True

    entities_for_tutor = ctrl.schedulable_entities(tutor_id=seeded["active"])
    by_id = {e.entity_id: e for e in entities_for_tutor if e.entity_type == "student"}
    assert by_id[seeded["s1"]].assignable is True
    assert by_id[physics_student_id].assignable is False


def _gap_count_hours(hours: list[int]) -> int:
    if len(hours) <= 1:
        return 0
    sorted_hours = sorted(hours)
    return sum(
        sorted_hours[i + 1] - sorted_hours[i] - 1
        for i in range(len(sorted_hours) - 1)
    )


def test_auto_assign_keeps_compact_day_for_student_in_two_subjects(seeded) -> None:
    """Same person in two subjects should not get gapped hours on the same day."""
    from app.models import StudyGroup

    subject_ctrl = SubjectController()
    english_id = subject_ctrl.add_subject("אנגלית")
    subject_ctrl.set_weekly_hours(english_id, 1)

    TutorController().add_tutor_subject(
        seeded["active"], english_id, [GRADE], units_min=5, units_max=5
    )

    with session_scope() as session:
        math_student = session.get(Student, seeded["s1"])
        assert math_student is not None
        session.add(
            Student(
                name=math_student.name,
                national_id=math_student.national_id,
                grade=math_student.grade,
                class_number=math_student.class_number,
                units=5,
                study_level=4,
                subject_id=english_id,
            )
        )

    ScheduleController().auto_assign(clear_existing=True)

    person_key = math_student.national_id

    with session_scope() as session:
        students_by_id = {s.id: s for s in session.scalars(select(Student)).all()}
        group_member_keys: dict[int, frozenset[str]] = {}
        for group in session.scalars(select(StudyGroup)).all():
            group_member_keys[group.id] = frozenset(
                m.national_id for m in group.members
            )

        hours_by_day: dict[int, list[int]] = {}
        for slot in session.scalars(select(ScheduleSlot)).all():
            affected: set[str] = set()
            if slot.student_id is not None:
                student = students_by_id.get(slot.student_id)
                if student is not None:
                    affected.add(student.national_id)
            elif slot.study_group_id is not None:
                affected |= group_member_keys.get(slot.study_group_id, frozenset())

            if person_key not in affected:
                continue
            hours_by_day.setdefault(slot.day, []).append(slot.hour)

        for day, hours in hours_by_day.items():
            assert _gap_count_hours(hours) == 0, f"gap on day {day}: {hours}"
