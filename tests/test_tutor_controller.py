"""Tests for tutor subject/grade qualifications."""

from __future__ import annotations

import pytest

from app.controllers.tutor_controller import TutorController
from app.database import session_scope
from app.models import Subject, Tutor


def _make(subject_name: str, tutor_name: str) -> tuple[int, int]:
    with session_scope() as session:
        subject = Subject(name=subject_name)
        tutor = Tutor(name=tutor_name)
        session.add_all([subject, tutor])
        session.flush()
        return subject.id, tutor.id


def test_add_qualification_for_multiple_grades() -> None:
    subject_id, tutor_id = _make("מתמטיקה", "דנה")
    ctrl = TutorController()
    affected = ctrl.add_tutor_subject(
        tutor_id, subject_id, ["י'", 'י"א', 'י"ב'], units_min=3, units_max=5
    )
    assert affected == 3

    rows = ctrl.list_tutor_subjects(tutor_id)
    assert len(rows) == 3
    grades = {r["grade"] for r in rows}
    assert grades == {"י'", 'י"א', 'י"ב'}
    assert all(r["units_min"] == 3 and r["units_max"] == 5 for r in rows)


def test_update_existing_grade_units_range() -> None:
    subject_id, tutor_id = _make("אנגלית", "רונית")
    ctrl = TutorController()
    ctrl.add_tutor_subject(tutor_id, subject_id, ["י'"], units_min=3, units_max=4)
    ctrl.add_tutor_subject(tutor_id, subject_id, ["י'"], units_min=4, units_max=5)

    rows = ctrl.list_tutor_subjects(tutor_id)
    assert len(rows) == 1
    assert rows[0]["units_min"] == 4
    assert rows[0]["units_max"] == 5


def test_invalid_units_range_rejected() -> None:
    subject_id, tutor_id = _make("פיזיקה", "נועה")
    ctrl = TutorController()
    with pytest.raises(ValueError):
        ctrl.add_tutor_subject(
            tutor_id, subject_id, ["י'"], units_min=5, units_max=3
        )


def test_no_grades_rejected() -> None:
    subject_id, tutor_id = _make("כימיה", "תמר")
    with pytest.raises(ValueError):
        TutorController().add_tutor_subject(
            tutor_id, subject_id, [], units_min=3, units_max=5
        )


def test_list_tutors_summary_includes_grade_and_range() -> None:
    subject_id, tutor_id = _make("מתמטיקה", "מאיה")
    TutorController().add_tutor_subject(
        tutor_id, subject_id, ['י"א'], units_min=3, units_max=5
    )
    summary = TutorController().list_tutors()[0]["subjects_text"]
    assert "מתמטיקה" in summary
    assert 'י"א' in summary
    assert "3-5" in summary
