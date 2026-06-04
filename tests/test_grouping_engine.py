"""Tests for the smart grouping engine."""

from __future__ import annotations

from app.services.grouping_engine import StudentRef, suggest_groups


def _ref(i: int, grade: str, units: int, level: int, grouped: bool = False):
    return StudentRef(
        id=i,
        name=f"student{i}",
        grade=grade,
        units=units,
        study_level=level,
        already_grouped=grouped,
    )


def test_suggests_only_matching_buckets() -> None:
    students = [
        _ref(1, "י\"א", 5, 4),
        _ref(2, "י\"א", 5, 4),
        _ref(3, "י\"א", 5, 4),
        _ref(4, "י\"א", 3, 2),  # alone -> no group
        _ref(5, "ט'", 5, 4),  # different grade -> no group
    ]
    suggestions = suggest_groups(students)
    assert len(suggestions) == 1
    assert suggestions[0].size == 3
    assert suggestions[0].key.grade == "י\"א"


def test_excludes_already_grouped_students() -> None:
    students = [
        _ref(1, "י'", 4, 3, grouped=True),
        _ref(2, "י'", 4, 3),
    ]
    # Only one ungrouped student remains -> no suggestion (min size 2).
    assert suggest_groups(students) == []


def test_suggested_name_format() -> None:
    students = [_ref(1, "י\"ב", 5, 5), _ref(2, "י\"ב", 5, 5)]
    suggestion = suggest_groups(students)[0]
    name = suggestion.suggested_name("מתמטיקה")
    assert "מתמטיקה" in name and "י\"ב" in name and "5" in name


def test_no_max_size_keeps_one_large_group() -> None:
    students = [_ref(i, "י'", 5, 4) for i in range(7)]
    suggestions = suggest_groups(students, max_size=0)
    assert len(suggestions) == 1
    assert suggestions[0].size == 7


def test_max_size_splits_into_fewest_balanced_groups() -> None:
    students = [_ref(i, "י'", 5, 4) for i in range(9)]
    suggestions = suggest_groups(students, max_size=5)
    # 9 students, max 5 -> 2 groups, balanced (5 and 4), never a tiny leftover.
    assert len(suggestions) == 2
    sizes = sorted(s.size for s in suggestions)
    assert sizes == [4, 5]
    assert all(s.total == 2 for s in suggestions)
    assert {s.index for s in suggestions} == {1, 2}


def test_max_size_split_balances_evenly() -> None:
    students = [_ref(i, "י'", 5, 4) for i in range(6)]
    suggestions = suggest_groups(students, max_size=4)
    # 6 students, max 4 -> 2 balanced groups of 3 (not 4 and 2).
    assert sorted(s.size for s in suggestions) == [3, 3]


def test_split_group_names_are_distinct() -> None:
    students = [_ref(i, "י'", 5, 4) for i in range(6)]
    suggestions = suggest_groups(students, max_size=4)
    names = {s.suggested_name("אנגלית") for s in suggestions}
    assert len(names) == 2  # "קבוצה 1" / "קבוצה 2"
