"""Integration test: parse a workbook and persist it via the controller."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import COL_CLASS, COL_LEVEL, COL_NAME, COL_UNITS
from app.controllers.grouping_controller import GroupingController
from app.controllers.import_controller import ImportController


def test_import_then_group(tmp_path: Path) -> None:
    path = tmp_path / "english.xlsx"
    pd.DataFrame(
        [
            {COL_NAME: "דני", COL_CLASS: "יא2", COL_UNITS: 5, COL_LEVEL: 4},
            {COL_NAME: "רותם", COL_CLASS: "יא3", COL_UNITS: 5, COL_LEVEL: 4},
            {COL_NAME: "יואב", COL_CLASS: "ט1", COL_UNITS: 3, COL_LEVEL: 2},
        ]
    ).to_excel(path, index=False)

    importer = ImportController()
    result = importer.parse_file(path)
    summary = importer.commit_import("אנגלית", result)
    assert summary.imported == 3

    subjects = importer.list_subjects()
    assert any(name == "אנגלית" for _id, name in subjects)
    subject_id = next(sid for sid, name in subjects if name == "אנגלית")

    students = importer.students_for_subject(subject_id)
    assert len(students) == 3

    grouping = GroupingController()
    suggestions = grouping.suggestions_for_subject(subject_id)
    # דני + רותם share grade/units/level -> one suggested group of size 2.
    assert len(suggestions) == 1
    assert suggestions[0].size == 2

    grouping.create_group(subject_id, suggestions[0])
    groups = grouping.list_groups(subject_id)
    assert len(groups) == 1
    assert len(groups[0]["members"]) == 2


def test_add_update_delete_student() -> None:
    ctrl = ImportController()
    subjects = ctrl.list_subjects()
    if not subjects:
        from app.controllers.subject_controller import SubjectController

        subject_id = SubjectController().add_subject("מתמטיקה")
    else:
        subject_id = subjects[0][0]

    student_id = ctrl.add_student(
        subject_id, "חדש", 'י"א', 3, 5, 4, preferred_tutor_id=None
    )
    students = ctrl.students_for_subject(subject_id)
    assert any(s["id"] == student_id and s["name"] == "חדש" for s in students)

    result = ctrl.update_student(
        student_id, "מעודכן", 'י"א', 3, 5, 4, preferred_tutor_id=None
    )
    assert not result.removed_from_group
    updated = ctrl.get_student(student_id)
    assert updated is not None
    assert updated["name"] == "מעודכן"

    ctrl.delete_student(student_id)
    assert ctrl.get_student(student_id) is None


def test_update_removes_from_group_on_grouping_field_change() -> None:
    ctrl = ImportController()
    grouping = GroupingController()
    from app.controllers.subject_controller import SubjectController

    subject_id = SubjectController().add_subject("היסטוריה")
    s1 = ctrl.add_student(subject_id, "א", 'י"א', 1, 5, 4)
    s2 = ctrl.add_student(subject_id, "ב", 'י"א', 2, 5, 4)
    group_id = grouping.create_manual_group(subject_id, "ג", [s1, s2])

    result = ctrl.update_student(s1, "א", 'י"ב', 1, 5, 4, preferred_tutor_id=None)
    assert result.removed_from_group
    student = ctrl.get_student(s1)
    assert student is not None
    assert student["study_group_id"] is None
    assert len(grouping.group_members(group_id)) == 1


def test_preferred_tutor_blocked_for_grouped_student() -> None:
    import pytest

    ctrl = ImportController()
    grouping = GroupingController()
    from app.controllers.subject_controller import SubjectController
    from app.database import session_scope
    from app.models import Tutor

    subject_id = SubjectController().add_subject("ספרות")
    s1 = ctrl.add_student(subject_id, "ג", 'י"א', 1, 5, 4)
    s2 = ctrl.add_student(subject_id, "ד", 'י"א', 2, 5, 4)
    grouping.create_manual_group(subject_id, "קבוצה", [s1, s2])

    with session_scope() as session:
        tutor = Tutor(name="חונכת")
        session.add(tutor)
        session.flush()
        tutor_id = tutor.id

    with pytest.raises(ValueError, match="קבוצת לימוד"):
        ctrl.set_student_preferred_tutor(s1, tutor_id)
