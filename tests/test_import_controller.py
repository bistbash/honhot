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
