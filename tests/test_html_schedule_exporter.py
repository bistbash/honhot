"""Tests for the interactive HTML schedule export."""

from __future__ import annotations

from pathlib import Path

from app.controllers.export_controller import ExportController
from app.database import session_scope
from app.models import EntityType, ScheduleSlot, Student, StudyGroup, Subject, Tutor
from app.services.html_schedule_exporter import build_interactive_html, cell_key

GRADE = 'י"א'


def _seed_schedule() -> dict[str, int]:
    with session_scope() as session:
        math = Subject(name="מתמטיקה")
        english = Subject(name="אנגלית")
        session.add_all([math, english])
        session.flush()

        tutor_a = Tutor(name="מאיה")
        tutor_b = Tutor(name="שרה")
        session.add_all([tutor_a, tutor_b])
        session.flush()

        dana = Student(
            name="דנה",
            national_id="123456782",
            grade=GRADE,
            class_number=1,
            units=5,
            study_level=4,
            subject_id=math.id,
        )
        ron = Student(
            name="רון",
            national_id="234567899",
            grade=GRADE,
            class_number=2,
            units=5,
            study_level=3,
            subject_id=math.id,
        )
        yael = Student(
            name="יעל",
            national_id="567890124",
            grade=GRADE,
            class_number=3,
            units=5,
            study_level=4,
            subject_id=english.id,
        )
        session.add_all([dana, ron, yael])
        session.flush()

        group = StudyGroup(
            name="קבוצת מתמטיקה",
            grade=GRADE,
            units=5,
            study_level=4,
            subject_id=math.id,
        )
        session.add(group)
        session.flush()
        ron.study_group_id = group.id

        session.add_all(
            [
                ScheduleSlot(
                    tutor_id=tutor_a.id,
                    day=2,
                    hour=3,
                    subject_id=math.id,
                    entity_type=EntityType.STUDENT,
                    student_id=dana.id,
                ),
                ScheduleSlot(
                    tutor_id=tutor_b.id,
                    day=2,
                    hour=3,
                    subject_id=math.id,
                    entity_type=EntityType.GROUP,
                    study_group_id=group.id,
                ),
                ScheduleSlot(
                    tutor_id=tutor_a.id,
                    day=0,
                    hour=1,
                    subject_id=english.id,
                    entity_type=EntityType.STUDENT,
                    student_id=yael.id,
                ),
            ]
        )
        session.flush()
        return {
            "math": math.id,
            "english": english.id,
            "tutor_a": tutor_a.id,
            "tutor_b": tutor_b.id,
            "dana": dana.id,
            "ron": ron.id,
            "yael": yael.id,
            "group": group.id,
        }


def test_build_html_payload_includes_all_view_kinds() -> None:
    ids = _seed_schedule()
    payload = ExportController().build_html_payload()

    kinds = {sheet.kind for sheet in payload.sheets}
    assert kinds == {"tutor", "subject", "student"}

    tutor_names = {
        sheet.name for sheet in payload.sheets if sheet.kind == "tutor"
    }
    assert tutor_names == {"מאיה", "שרה"}

    student_sheets = [s for s in payload.sheets if s.kind == "student"]
    assert len(student_sheets) == 3
    assert len({s.national_id for s in student_sheets}) == 3

    student_names = {sheet.name for sheet in student_sheets}
    assert any("דנה" in name for name in student_names)
    assert any("רון" in name for name in student_names)
    ron_sheet = next(
        s for s in student_sheets if s.national_id == "234567899"
    )
    assert ron_sheet.national_id == "234567899"


def test_student_in_group_sees_group_lesson() -> None:
    ids = _seed_schedule()
    payload = ExportController().build_html_payload()
    ron_sheet = next(
        s for s in payload.sheets if s.kind == "student" and s.national_id == "234567899"
    )
    key = cell_key(2, 3)
    assert key in ron_sheet.cells
    block = ron_sheet.cells[key][0]
    assert block.subject == "מתמטיקה"
    assert block.tutor == "שרה"
    assert "רון" in block.students[0]
    assert "234567899" in block.students[0]


def test_subject_view_has_multiple_blocks_in_same_cell() -> None:
    ids = _seed_schedule()
    payload = ExportController().build_html_payload()
    math_sheet = next(
        s for s in payload.sheets if s.kind == "subject" and s.id == ids["math"]
    )
    key = cell_key(2, 3)
    assert len(math_sheet.cells[key]) == 2
    tutors = {block.tutor for block in math_sheet.cells[key]}
    assert tutors == {"מאיה", "שרה"}


def test_build_interactive_html_contains_rtl_and_embedded_data() -> None:
    _seed_schedule()
    payload = ExportController().build_html_payload()
    html_text = build_interactive_html(payload)

    assert 'dir="rtl"' in html_text
    assert 'type="application/json"' in html_text
    assert "מאיה" in html_text
    assert "דנה" in html_text
    assert 'id="studentSearch"' in html_text
    assert "national_id" in html_text
    assert "חונכות" in html_text
    assert "מקצועות" in html_text
    assert "תלמידים" in html_text


def test_student_sheet_merges_same_person_across_subjects() -> None:
    with session_scope() as session:
        math = Subject(name="מתמטיקה")
        english = Subject(name="אנגלית")
        session.add_all([math, english])
        session.flush()

        tutor = Tutor(name="מאיה")
        session.add(tutor)
        session.flush()

        shared_id = "123456782"
        dana_math = Student(
            name="דנה כהן",
            national_id=shared_id,
            grade=GRADE,
            class_number=1,
            units=5,
            study_level=4,
            subject_id=math.id,
        )
        dana_english = Student(
            name="דנה כהן",
            national_id=shared_id,
            grade=GRADE,
            class_number=1,
            units=4,
            study_level=3,
            subject_id=english.id,
        )
        session.add_all([dana_math, dana_english])
        session.flush()

        session.add_all(
            [
                ScheduleSlot(
                    tutor_id=tutor.id,
                    day=1,
                    hour=2,
                    subject_id=math.id,
                    entity_type=EntityType.STUDENT,
                    student_id=dana_math.id,
                ),
                ScheduleSlot(
                    tutor_id=tutor.id,
                    day=3,
                    hour=4,
                    subject_id=english.id,
                    entity_type=EntityType.STUDENT,
                    student_id=dana_english.id,
                ),
            ]
        )

    payload = ExportController().build_html_payload()
    dana_sheets = [
        s for s in payload.sheets if s.kind == "student" and s.national_id == shared_id
    ]
    assert len(dana_sheets) == 1
    sheet = dana_sheets[0]
    assert cell_key(1, 2) in sheet.cells
    assert cell_key(3, 4) in sheet.cells
    subjects = {
        block.subject
        for blocks in sheet.cells.values()
        for block in blocks
    }
    assert subjects == {"מתמטיקה", "אנגלית"}


def test_export_html_site_writes_file(tmp_path: Path) -> None:
    _seed_schedule()
    out = tmp_path / "schedule.html"
    ExportController().export_html_site(out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "schedule-data" in content
