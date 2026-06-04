"""Smart grouping engine.

Analyses students within a subject and suggests study groups: students who
share the exact same grade, units and study level. To keep tutoring efficient
the engine prefers the **fewest, largest** groups. When an optional maximum
group size is supplied, an oversized bucket is split into the minimum number of
**balanced** groups (sizes differ by at most one) so no tiny leftover groups
are created. Pure logic, no Qt.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupKey:
    """The attributes that define a study group within a subject."""

    grade: str
    units: int
    study_level: int


@dataclass
class StudentRef:
    """Lightweight reference to a student used by the grouping engine."""

    id: int
    name: str
    grade: str
    units: int
    study_level: int
    already_grouped: bool = False


@dataclass
class GroupSuggestion:
    """A suggested study group: a key plus the matching ungrouped students.

    ``index``/``total`` describe the group's position when a single key is split
    into several balanced groups (1-based). ``total == 1`` means no split.
    """

    key: GroupKey
    members: list[StudentRef]
    index: int = 1
    total: int = 1

    @property
    def size(self) -> int:
        return len(self.members)

    def suggested_name(self, subject_name: str) -> str:
        """Build a human-readable default name for the group."""
        base = (
            f"{subject_name} - {self.key.grade} - "
            f"{self.key.units} יח\"ל - רמה {self.key.study_level}"
        )
        if self.total > 1:
            base += f" - קבוצה {self.index}"
        return base


def _balanced_split(
    members: list[StudentRef], max_size: int
) -> list[list[StudentRef]]:
    """Split members into the fewest balanced chunks, each at most ``max_size``."""
    count = len(members)
    groups = -(-count // max_size)  # ceil division
    base, remainder = divmod(count, groups)
    chunks: list[list[StudentRef]] = []
    start = 0
    for k in range(groups):
        size = base + (1 if k < remainder else 0)
        chunks.append(members[start : start + size])
        start += size
    return chunks


def suggest_groups(
    students: list[StudentRef], min_size: int = 2, max_size: int = 0
) -> list[GroupSuggestion]:
    """Bucket ungrouped students by (grade, units, study_level).

    Args:
        students: candidate students (already-grouped ones are ignored).
        min_size: minimum members for a bucket to be worth grouping.
        max_size: maximum members per group; ``<= 0`` means no limit (one large
            group per key). Oversized buckets are split into balanced groups.

    Returns buckets with at least ``min_size`` members, sorted by descending
    size then by key for stable, predictable ordering.
    """
    buckets: dict[GroupKey, list[StudentRef]] = defaultdict(list)
    for student in students:
        if student.already_grouped:
            continue
        key = GroupKey(student.grade, student.units, student.study_level)
        buckets[key].append(student)

    suggestions: list[GroupSuggestion] = []
    for key, members in buckets.items():
        if len(members) < min_size:
            continue
        ordered = sorted(members, key=lambda m: (m.name, m.id))
        if max_size and len(ordered) > max_size:
            chunks = _balanced_split(ordered, max_size)
            total = len(chunks)
            for i, chunk in enumerate(chunks, start=1):
                suggestions.append(
                    GroupSuggestion(key=key, members=chunk, index=i, total=total)
                )
        else:
            suggestions.append(GroupSuggestion(key=key, members=ordered))

    suggestions.sort(
        key=lambda s: (
            -s.size,
            s.key.grade,
            s.key.units,
            s.key.study_level,
            s.index,
        )
    )
    return suggestions
