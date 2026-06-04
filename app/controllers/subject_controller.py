"""Controller for subject reserved time windows."""

from __future__ import annotations

from sqlalchemy import select

from app.database import session_scope
from app.models import Subject, SubjectTimeWindow


class SubjectController:
    """Manages subjects, their weekly hours and reserved (day, hour) windows."""

    def list_subjects(self) -> list[tuple[int, str]]:
        with session_scope() as session:
            rows = session.scalars(select(Subject).order_by(Subject.name)).all()
            return [(s.id, s.name) for s in rows]

    def list_subjects_detailed(self) -> list[dict]:
        """Return subjects with their weekly hours for management views."""
        with session_scope() as session:
            rows = session.scalars(select(Subject).order_by(Subject.name)).all()
            return [
                {"id": s.id, "name": s.name, "weekly_hours": s.weekly_hours}
                for s in rows
            ]

    def add_subject(self, name: str, weekly_hours: int = 1) -> int:
        """Create a subject manually (without importing students)."""
        name = name.strip()
        if not name:
            raise ValueError("יש להזין שם מקצוע")
        if weekly_hours < 1:
            raise ValueError("שעות שבועיות חייבות להיות 1 ומעלה")
        with session_scope() as session:
            existing = session.scalar(select(Subject).where(Subject.name == name))
            if existing is not None:
                raise ValueError("מקצוע בשם זה כבר קיים")
            subject = Subject(name=name, weekly_hours=weekly_hours)
            session.add(subject)
            session.flush()
            return subject.id

    def rename_subject(self, subject_id: int, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("יש להזין שם מקצוע")
        with session_scope() as session:
            clash = session.scalar(
                select(Subject).where(
                    Subject.name == new_name, Subject.id != subject_id
                )
            )
            if clash is not None:
                raise ValueError("מקצוע בשם זה כבר קיים")
            subject = session.get(Subject, subject_id)
            if subject is not None:
                subject.name = new_name

    def get_weekly_hours(self, subject_id: int) -> int:
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            return subject.weekly_hours if subject else 1

    def set_weekly_hours(self, subject_id: int, weekly_hours: int) -> None:
        if weekly_hours < 1:
            raise ValueError("שעות שבועיות חייבות להיות 1 ומעלה")
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is not None:
                subject.weekly_hours = weekly_hours

    def delete_subject(self, subject_id: int) -> None:
        """Delete a subject and all dependent records (students, slots, etc.)."""
        with session_scope() as session:
            subject = session.get(Subject, subject_id)
            if subject is not None:
                session.delete(subject)

    def get_windows(self, subject_id: int) -> set[tuple[int, int]]:
        """Return the set of reserved (day, hour) cells for a subject."""
        with session_scope() as session:
            rows = session.scalars(
                select(SubjectTimeWindow).where(
                    SubjectTimeWindow.subject_id == subject_id
                )
            ).all()
            return {(w.day, w.hour) for w in rows}

    def set_windows(self, subject_id: int, cells: set[tuple[int, int]]) -> None:
        """Replace the subject's reserved windows with the given set of cells."""
        with session_scope() as session:
            session.query(SubjectTimeWindow).filter(
                SubjectTimeWindow.subject_id == subject_id
            ).delete()
            for day, hour in sorted(cells):
                session.add(
                    SubjectTimeWindow(subject_id=subject_id, day=day, hour=hour)
                )
