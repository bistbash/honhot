"""Tests for manual study-group creation and editing."""

from __future__ import annotations

import pytest

from app.controllers.grouping_controller import (
    GroupingController,
    filter_group_compatible,
    student_group_compatible,
)
from app.database import session_scope
from app.models import Student, Subject

GRADE = 'י"א'


def _seed():
    """Create a subject with several ungrouped students for grouping."""
    with session_scope() as session:
        subject = Subject(name="מתמטיקה")
        session.add(subject)
        session.flush()
        students = [
            Student(name="דנה", grade=GRADE, class_number=1, units=5,
                    study_level=4, subject_id=subject.id),
            Student(name="רון", grade=GRADE, class_number=1, units=5,
                    study_level=3, subject_id=subject.id),
            Student(name="מאיה", grade=GRADE, class_number=2, units=5,
                    study_level=4, subject_id=subject.id),
            Student(name="עידן", grade="י'", class_number=1, units=4,
                    study_level=3, subject_id=subject.id),
        ]
        session.add_all(students)
        session.flush()
        return subject.id, [s.id for s in students]


def test_create_manual_group_with_uniform_students() -> None:
    subject_id, ids = _seed()
    ctrl = GroupingController()
    group_id = ctrl.create_manual_group(subject_id, "קבוצה א", ids[:3])
    members = ctrl.group_members(group_id)
    assert len(members) == 3
    # The grouped students are no longer offered as ungrouped.
    ungrouped = {s["id"] for s in ctrl.list_ungrouped_students(subject_id)}
    assert ungrouped == {ids[3]}


def test_create_manual_group_rejects_mixed_grade() -> None:
    subject_id, ids = _seed()
    ctrl = GroupingController()
    with pytest.raises(ValueError):
        # ids[0] is grade י"א, ids[3] is grade י'.
        ctrl.create_manual_group(subject_id, "", [ids[0], ids[3]])


def test_edit_group_membership() -> None:
    subject_id, ids = _seed()
    ctrl = GroupingController()
    group_id = ctrl.create_manual_group(subject_id, "קבוצה", ids[:2])
    # Replace members: drop ids[1], add ids[2].
    ctrl.set_group_members(group_id, "קבוצה חדשה", [ids[0], ids[2]])
    members = {m["id"] for m in ctrl.group_members(group_id)}
    assert members == {ids[0], ids[2]}
    ungrouped = {s["id"] for s in ctrl.list_ungrouped_students(subject_id)}
    assert ids[1] in ungrouped  # returned to the pool


def test_create_manual_group_requires_members() -> None:
    subject_id, _ids = _seed()
    with pytest.raises(ValueError):
        GroupingController().create_manual_group(subject_id, "ריק", [])


def test_group_preferred_tutor_persisted() -> None:
    subject_id, ids = _seed()
    ctrl = GroupingController()
    with session_scope() as session:
        from app.models import Tutor

        tutor = Tutor(name="רות")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id

    group_id = ctrl.create_manual_group(
        subject_id, "קבוצה א", ids[:2], preferred_tutor_id=tutor_id
    )
    group = ctrl.get_group(group_id)
    assert group is not None
    assert group["name"] == "קבוצה א"
    assert group["preferred_tutor_id"] == tutor_id


def test_inherit_preferred_tutor_from_members() -> None:
    subject_id, ids = _seed()
    with session_scope() as session:
        from app.models import Tutor

        tutor = Tutor(name="נועה")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id
        for sid in ids[:2]:
            student = session.get(Student, sid)
            assert student is not None
            student.preferred_tutor_id = tutor_id

    ctrl = GroupingController()
    group_id = ctrl.create_manual_group(subject_id, "קבוצה ב", ids[:2])
    group = ctrl.get_group(group_id)
    assert group is not None
    assert group["preferred_tutor_id"] == tutor_id


def test_set_group_details_updates_name_and_tutor() -> None:
    subject_id, ids = _seed()
    ctrl = GroupingController()
    group_id = ctrl.create_manual_group(subject_id, "שם ישן", ids[:2])
    with session_scope() as session:
        from app.models import Tutor

        tutor = Tutor(name="דנה")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id

    ctrl.set_group_details(group_id, "שם חדש", preferred_tutor_id=tutor_id)
    group = ctrl.get_group(group_id)
    assert group is not None
    assert group["name"] == "שם חדש"
    assert group["preferred_tutor_id"] == tutor_id


def test_filter_group_compatible_matches_grade_and_units() -> None:
    students = [
        {"id": 1, "grade": GRADE, "units": 5, "study_level": 4},
        {"id": 2, "grade": GRADE, "units": 5, "study_level": 3},
        {"id": 3, "grade": "י'", "units": 4, "study_level": 3},
        {"id": 4, "grade": GRADE, "units": 4, "study_level": 3},
    ]
    matched = filter_group_compatible(students, GRADE, 5)
    assert {s["id"] for s in matched} == {1, 2}
    assert student_group_compatible(students[1], GRADE, 5)
    assert not student_group_compatible(students[2], GRADE, 5)
