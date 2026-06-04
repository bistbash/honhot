"""Controller for importing subject workbooks into the database."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.database import session_scope
from app.models import Student, Subject
from app.services.excel_parser import ImportResult, parse_workbook, write_template


@dataclass
class CommitSummary:
    """Result of committing an import to the database."""

    subject_name: str
    imported: int
    skipped_issues: int


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
                    "grade": s.grade,
                    "class_number": s.class_number,
                    "units": s.units,
                    "study_level": s.study_level,
                    "group": s.study_group.name if s.study_group else "",
                }
                for s in students
            ]

    def delete_subject(self, subject_id: int) -> None:
        """Delete a subject and all of its dependent records."""
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is not None:
                session.delete(subject)
