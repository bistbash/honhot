"""Tests for the Excel parsing service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import (
    COL_CLASS,
    COL_LEVEL,
    COL_NAME,
    COL_UNITS,
    GRADE_TET,
    GRADE_YA,
    GRADE_YB,
    GRADE_YOD,
)
from app.services.excel_parser import (
    ExcelImportError,
    parse_class_token,
    parse_workbook,
    write_template,
)


@pytest.mark.parametrize(
    "token,expected",
    [
        ("ט1", (GRADE_TET, 1)),
        ("יב2", (GRADE_YB, 2)),
        ('י"ב4', (GRADE_YB, 4)),
        ('י"א5', (GRADE_YA, 5)),
        ("יא2", (GRADE_YA, 2)),
        ("י1", (GRADE_YOD, 1)),
        ("י'1", (GRADE_YOD, 1)),
        ("ט'1", (GRADE_TET, 1)),
        ("  יא 10 ", (GRADE_YA, 10)),
    ],
)
def test_parse_class_token_valid(token: str, expected: tuple[str, int]) -> None:
    assert parse_class_token(token) == expected


@pytest.mark.parametrize("token", ["", "abc", "5", "ק3", None])
def test_parse_class_token_invalid(token: str) -> None:
    with pytest.raises(ValueError):
        parse_class_token(token)


def test_write_template_is_valid_and_parseable(tmp_path: Path) -> None:
    """The generated template must import cleanly with no issues."""
    path = tmp_path / "template.xlsx"
    write_template(path)
    assert path.exists()

    result = parse_workbook(path)
    assert not result.has_issues
    assert len(result.students) >= 1
    # Sanity-check one of the example rows parsed correctly.
    assert result.students[0].grade in {GRADE_TET, GRADE_YOD, GRADE_YA, GRADE_YB}


def _write_workbook(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)


def test_parse_workbook_success(tmp_path: Path) -> None:
    path = tmp_path / "math.xlsx"
    _write_workbook(
        path,
        [
            {COL_NAME: "דני", COL_CLASS: "יא2", COL_UNITS: 5, COL_LEVEL: 4},
            {COL_NAME: "רותם", COL_CLASS: 'י"ב4', COL_UNITS: 3, COL_LEVEL: 2},
        ],
    )
    result = parse_workbook(path)
    assert len(result.students) == 2
    assert not result.has_issues
    assert result.students[0].grade == GRADE_YA
    assert result.students[0].units == 5


def test_parse_workbook_reports_row_issues(tmp_path: Path) -> None:
    path = tmp_path / "bad.xlsx"
    _write_workbook(
        path,
        [
            {COL_NAME: "תקין", COL_CLASS: "ט1", COL_UNITS: 5, COL_LEVEL: 3},
            {COL_NAME: "יחל גבוה", COL_CLASS: "ט1", COL_UNITS: 9, COL_LEVEL: 3},
            {COL_NAME: "כיתה פגומה", COL_CLASS: "???", COL_UNITS: 5, COL_LEVEL: 3},
        ],
    )
    result = parse_workbook(path)
    assert len(result.students) == 1
    assert len(result.issues) == 2


def test_parse_workbook_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "missing.xlsx"
    _write_workbook(path, [{COL_NAME: "דני", COL_CLASS: "ט1"}])
    with pytest.raises(ExcelImportError):
        parse_workbook(path)
