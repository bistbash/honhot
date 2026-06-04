"""Controller for the smart grouping workflow."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from app.database import session_scope
from app.models import Student, StudyGroup, Subject
from app.services.grouping_engine import (
    GroupSuggestion,
    StudentRef,
    suggest_groups,
)


def _student_dict(student: Student) -> dict:
    """Serialize a student for selection lists."""
    return {
        "id": student.id,
        "name": student.name,
        "grade": student.grade,
        "units": student.units,
        "study_level": student.study_level,
        "label": (
            f"{student.name}  ({student.grade}{student.class_number})  ·  "
            f"{student.units} יח\"ל  ·  רמה {student.study_level}"
        ),
    }


def _validate_uniform(students: list[Student]) -> tuple[str, int, int]:
    """Ensure students share grade + units; return (grade, units, level).

    A group is scheduled by a single grade + units (tutor qualification), so a
    manual group must be uniform on those. ``study_level`` may differ; the most
    common one is used as the group's nominal level.
    """
    if not students:
        raise ValueError("יש לבחור לפחות תלמיד אחד לקבוצה")
    grades = {s.grade for s in students}
    units = {s.units for s in students}
    if len(grades) > 1:
        raise ValueError(
            "לא ניתן לשלב שכבות שונות בקבוצה אחת: " + ", ".join(sorted(grades))
        )
    if len(units) > 1:
        raise ValueError(
            'לא ניתן לשלב יח"ל שונים בקבוצה אחת: '
            + ", ".join(str(u) for u in sorted(units))
        )
    level = Counter(s.study_level for s in students).most_common(1)[0][0]
    return next(iter(grades)), next(iter(units)), level


class GroupingController:
    """Suggests and creates study groups within a subject."""

    def list_subjects(self) -> list[tuple[int, str]]:
        with session_scope() as session:
            rows = session.scalars(select(Subject).order_by(Subject.name)).all()
            return [(s.id, s.name) for s in rows]

    def suggestions_for_subject(
        self, subject_id: int, max_size: int = 0
    ) -> list[GroupSuggestion]:
        """Return suggested groups for the subject's currently ungrouped students.

        ``max_size <= 0`` produces the fewest, largest groups; a positive value
        caps group size and splits oversized buckets into balanced groups.
        """
        with session_scope() as session:
            students = session.scalars(
                select(Student).where(Student.subject_id == subject_id)
            ).all()
            refs = [
                StudentRef(
                    id=s.id,
                    name=s.name,
                    grade=s.grade,
                    units=s.units,
                    study_level=s.study_level,
                    already_grouped=s.study_group_id is not None,
                )
                for s in students
            ]
        return suggest_groups(refs, max_size=max_size)

    def create_group(
        self, subject_id: int, suggestion: GroupSuggestion, name: str | None = None
    ) -> int:
        """Create a StudyGroup from a suggestion and attach its members.

        Returns the new group id.
        """
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is None:
                raise ValueError("המקצוע לא נמצא")

            group_name = (name or "").strip() or suggestion.suggested_name(
                subject.name
            )
            group = StudyGroup(
                name=group_name,
                grade=suggestion.key.grade,
                units=suggestion.key.units,
                study_level=suggestion.key.study_level,
                subject_id=subject_id,
            )
            session.add(group)
            session.flush()

            member_ids = [m.id for m in suggestion.members]
            members = session.scalars(
                select(Student).where(Student.id.in_(member_ids))
            ).all()
            for student in members:
                # Only group students that are still ungrouped.
                if student.study_group_id is None:
                    student.study_group_id = group.id

            return group.id

    def list_groups(self, subject_id: int) -> list[dict]:
        """Return existing groups for a subject with member counts."""
        with session_scope() as session:
            groups = session.scalars(
                select(StudyGroup)
                .where(StudyGroup.subject_id == subject_id)
                .order_by(StudyGroup.name)
            ).all()
            return [
                {
                    "id": g.id,
                    "name": g.name,
                    "grade": g.grade,
                    "units": g.units,
                    "study_level": g.study_level,
                    "members": [m.name for m in g.members],
                }
                for g in groups
            ]

    def disband_group(self, group_id: int) -> None:
        """Delete a group, returning its members to the ungrouped pool."""
        with session_scope() as session:
            group = session.get(StudyGroup, group_id)
            if group is None:
                return
            for member in list(group.members):
                member.study_group_id = None
            session.delete(group)

    # ----------------------------------------------------- manual editing
    def list_ungrouped_students(self, subject_id: int) -> list[dict]:
        """Return ungrouped students of a subject for manual group building."""
        with session_scope() as session:
            rows = session.scalars(
                select(Student)
                .where(
                    Student.subject_id == subject_id,
                    Student.study_group_id.is_(None),
                )
                .order_by(Student.grade, Student.units, Student.name)
            ).all()
            return [_student_dict(s) for s in rows]

    def group_members(self, group_id: int) -> list[dict]:
        """Return the members of an existing group."""
        with session_scope() as session:
            group = session.get(StudyGroup, group_id)
            if group is None:
                return []
            return [_student_dict(s) for s in group.members]

    def get_group(self, group_id: int) -> dict | None:
        with session_scope() as session:
            group = session.get(StudyGroup, group_id)
            if group is None:
                return None
            return {
                "id": group.id,
                "name": group.name,
                "subject_id": group.subject_id,
                "grade": group.grade,
                "units": group.units,
                "study_level": group.study_level,
            }

    def create_manual_group(
        self, subject_id: int, name: str, student_ids: list[int]
    ) -> int:
        """Create a group from a hand-picked set of students.

        The selected students must share grade + units. Returns the group id.
        """
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is None:
                raise ValueError("המקצוע לא נמצא")

            students = session.scalars(
                select(Student).where(
                    Student.id.in_(student_ids),
                    Student.subject_id == subject_id,
                )
            ).all()
            grade, units, level = _validate_uniform(students)

            blocked = [s.name for s in students if s.study_group_id is not None]
            if blocked:
                raise ValueError(
                    "תלמידים שכבר משובצים בקבוצה: " + ", ".join(blocked)
                )

            group_name = (name or "").strip() or (
                f"{subject.name} - {grade} - {units} יח\"ל"
            )
            group = StudyGroup(
                name=group_name,
                grade=grade,
                units=units,
                study_level=level,
                subject_id=subject_id,
            )
            session.add(group)
            session.flush()
            for student in students:
                student.study_group_id = group.id
            return group.id

    def set_group_members(
        self, group_id: int, name: str, student_ids: list[int]
    ) -> None:
        """Replace a group's members and name (for manual editing)."""
        with session_scope() as session:
            group = session.get(StudyGroup, group_id)
            if group is None:
                raise ValueError("הקבוצה לא נמצאה")

            students = session.scalars(
                select(Student).where(
                    Student.id.in_(student_ids),
                    Student.subject_id == group.subject_id,
                )
            ).all()
            grade, units, level = _validate_uniform(students)

            foreign = [
                s.name
                for s in students
                if s.study_group_id not in (None, group.id)
            ]
            if foreign:
                raise ValueError(
                    "תלמידים שכבר משובצים בקבוצה אחרת: " + ", ".join(foreign)
                )

            keep = set(student_ids)
            for member in list(group.members):
                if member.id not in keep:
                    member.study_group_id = None
            for student in students:
                student.study_group_id = group.id

            group.name = (name or "").strip() or group.name
            group.grade = grade
            group.units = units
            group.study_level = level
