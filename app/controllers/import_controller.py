"""Controller for importing subject workbooks into the database."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.config import GRADES, LEVEL_MAX, LEVEL_MIN, UNITS_MAX, UNITS_MIN
from app.database import session_scope
from app.models import Student, Subject, Tutor
from app.services.excel_parser import ImportResult, parse_workbook, write_template
from app.services.national_id import validate_national_id


@dataclass
class CommitSummary:
    """Result of committing an import to the database."""

    subject_name: str
    imported: int
    skipped_issues: int


@dataclass
class StudentUpdateResult:
    """Outcome of updating a student record."""

    removed_from_group: bool = False


def _validate_student_fields(
    name: str,
    national_id: str,
    grade: str,
    class_number: int,
    units: int,
    study_level: int,
) -> str:
    name = name.strip()
    if not name:
        raise ValueError("יש להזין שם תלמיד")
    normalized_id = validate_national_id(national_id)
    if grade not in GRADES:
        raise ValueError(f"שכבה לא חוקית: {grade}")
    if not 1 <= class_number <= 15:
        raise ValueError("מספר כיתה חייב להיות בין 1 ל-15")
    if not UNITS_MIN <= units <= UNITS_MAX:
        raise ValueError(f'יח"ל חייב להיות בין {UNITS_MIN} ל-{UNITS_MAX}')
    if not LEVEL_MIN <= study_level <= LEVEL_MAX:
        raise ValueError(f"רמת לימוד חייבת להיות בין {LEVEL_MIN} ל-{LEVEL_MAX}")
    return normalized_id


class ImportController:
    """Coordinates Excel parsing and persistence of students under a subject."""

    def parse_file(self, file_path: str | Path) -> ImportResult:
        """Parse a workbook without touching the database."""
        return parse_workbook(file_path)

    def create_template(self, file_path: str | Path) -> Path:
        """Write a sample import workbook to ``file_path``."""
        return write_template(file_path)

    def commit_import(
        self, subject_name: str, result: ImportResult
    ) -> CommitSummary:
        """Persist parsed students under a subject, creating it if needed.

        Students are appended to the subject; importing the same file twice
        will add duplicate rows, which is acceptable for this workflow.
        """
        subject_name = subject_name.strip()
        if not subject_name:
            raise ValueError("יש להזין שם מקצוע")

        with session_scope() as session:
            subject = session.scalar(
                select(Subject).where(Subject.name == subject_name)
            )
            if subject is None:
                subject = Subject(name=subject_name)
                session.add(subject)
                session.flush()

            for parsed in result.students:
                session.add(
                    Student(
                        name=parsed.name,
                        national_id=parsed.national_id,
                        grade=parsed.grade,
                        class_number=parsed.class_number,
                        units=parsed.units,
                        study_level=parsed.study_level,
                        subject_id=subject.id,
                    )
                )

        return CommitSummary(
            subject_name=subject_name,
            imported=len(result.students),
            skipped_issues=len(result.issues),
        )

    def list_subjects(self) -> list[tuple[int, str]]:
        """Return (id, name) for all subjects, ordered by name."""
        with session_scope() as session:
            rows = session.scalars(select(Subject).order_by(Subject.name)).all()
            return [(s.id, s.name) for s in rows]

    def students_for_subject(self, subject_id: int) -> list[dict]:
        """Return a list of student dicts for a subject for display in a table."""
        with session_scope() as session:
            students = session.scalars(
                select(Student)
                .where(Student.subject_id == subject_id)
                .order_by(Student.grade, Student.name)
            ).all()
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "national_id": s.national_id,
                    "grade": s.grade,
                    "class_number": s.class_number,
                    "units": s.units,
                    "study_level": s.study_level,
                    "group": s.study_group.name if s.study_group else "",
                    "study_group_id": s.study_group_id,
                    "subject_id": s.subject_id,
                    "preferred_tutor_id": s.preferred_tutor_id,
                    "preferred_tutor_name": (
                        s.preferred_tutor.name if s.preferred_tutor else ""
                    ),
                }
                for s in students
            ]

    def list_qualified_tutors(
        self, subject_id: int, grade: str, units: int
    ) -> list[tuple[int, str]]:
        """Return tutors qualified for the given subject, grade and units."""
        with session_scope() as session:
            tutors = session.scalars(select(Tutor).order_by(Tutor.name)).all()
            result: list[tuple[int, str]] = []
            for tutor in tutors:
                for qual in tutor.subjects:
                    if qual.subject_id == subject_id and qual.covers(grade, units):
                        result.append((tutor.id, tutor.name))
                        break
            return result

    def get_student(self, student_id: int) -> dict | None:
        with session_scope() as session:
            s = session.get(Student, student_id)
            if s is None:
                return None
            return {
                "id": s.id,
                "name": s.name,
                "national_id": s.national_id,
                "grade": s.grade,
                "class_number": s.class_number,
                "units": s.units,
                "study_level": s.study_level,
                "group": s.study_group.name if s.study_group else "",
                "study_group_id": s.study_group_id,
                "subject_id": s.subject_id,
                "preferred_tutor_id": s.preferred_tutor_id,
                "preferred_tutor_name": (
                    s.preferred_tutor.name if s.preferred_tutor else ""
                ),
            }

    def add_student(
        self,
        subject_id: int,
        name: str,
        national_id: str,
        grade: str,
        class_number: int,
        units: int,
        study_level: int,
        preferred_tutor_id: int | None = None,
    ) -> int:
        """Create a student manually under a subject. Returns the new student id."""
        normalized_id = _validate_student_fields(
            name, national_id, grade, class_number, units, study_level
        )
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is None:
                raise ValueError("המקצוע לא נמצא")
            if preferred_tutor_id is not None:
                if session.get(Tutor, preferred_tutor_id) is None:
                    raise ValueError("החונכת לא נמצאה")
            student = Student(
                name=name.strip(),
                national_id=normalized_id,
                grade=grade,
                class_number=class_number,
                units=units,
                study_level=study_level,
                subject_id=subject_id,
                preferred_tutor_id=preferred_tutor_id,
            )
            session.add(student)
            session.flush()
            return student.id

    def update_student(
        self,
        student_id: int,
        name: str,
        national_id: str,
        grade: str,
        class_number: int,
        units: int,
        study_level: int,
        preferred_tutor_id: int | None = None,
    ) -> StudentUpdateResult:
        """Update a student. Removes from group if grade/units/level change."""
        normalized_id = _validate_student_fields(
            name, national_id, grade, class_number, units, study_level
        )
        result = StudentUpdateResult()
        with session_scope() as session:
            student = session.get(Student, student_id)
            if student is None:
                raise ValueError("התלמיד לא נמצא")

            grouping_changed = (
                student.grade != grade
                or student.units != units
                or student.study_level != study_level
            )
            if student.study_group_id is not None:
                if preferred_tutor_id is not None:
                    raise ValueError(
                        "לתלמיד בקבוצת לימוד אין להגדיר חונכת מועדפת. "
                        "יש להגדיר בלשונית קבוצות לימוד."
                    )
                if grouping_changed:
                    student.study_group_id = None
                    result.removed_from_group = True

            student.name = name.strip()
            student.national_id = normalized_id
            student.grade = grade
            student.class_number = class_number
            student.units = units
            student.study_level = study_level
            if student.study_group_id is None:
                if preferred_tutor_id is not None:
                    if session.get(Tutor, preferred_tutor_id) is None:
                        raise ValueError("החונכת לא נמצאה")
                student.preferred_tutor_id = preferred_tutor_id
        return result

    def delete_student(self, student_id: int) -> None:
        """Delete a student and their schedule slots (cascade)."""
        with session_scope() as session:
            student = session.get(Student, student_id)
            if student is None:
                raise ValueError("התלמיד לא נמצא")
            session.delete(student)

    def set_student_preferred_tutor(
        self, student_id: int, tutor_id: int | None
    ) -> str | None:
        """Set a student's preferred tutor. Returns a warning message if unqualified."""
        warning: str | None = None
        with session_scope() as session:
            student = session.get(Student, student_id)
            if student is None:
                raise ValueError("התלמיד לא נמצא")
            if student.study_group_id is not None:
                raise ValueError(
                    "לתלמיד בקבוצת לימוד אין להגדיר חונכת מועדפת. "
                    "יש להגדיר בלשונית קבוצות לימוד."
                )
            if tutor_id is not None:
                tutor = session.get(Tutor, tutor_id)
                if tutor is None:
                    raise ValueError("החונכת לא נמצאה")
                qualified = any(
                    q.subject_id == student.subject_id
                    and q.covers(student.grade, student.units)
                    for q in tutor.subjects
                )
                if not qualified:
                    warning = (
                        f"החונכת {tutor.name} אינה מוסמכת ל"
                        f"{student.subject.name} {student.grade} "
                        f"({student.units} יח\"ל)."
                    )
            student.preferred_tutor_id = tutor_id
        return warning

    def delete_subject(self, subject_id: int) -> None:
        """Delete a subject and all of its dependent records."""
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is not None:
                session.delete(subject)
