"""Controller for managing tutors (create, rename, qualifications, constraints)."""

from __future__ import annotations

from sqlalchemy import select

from app.config import GRADES, UNITS_MAX, UNITS_MIN
from app.database import session_scope
from app.models import (
    GlobalUnavailability,
    Subject,
    Tutor,
    TutorSubject,
    TutorUnavailability,
)


def _summarize_quals(quals: list[TutorSubject]) -> str:
    """Build a compact one-line summary of a tutor's qualifications."""
    parts: list[str] = []
    valid = [q for q in quals if q.subject is not None]
    for q in sorted(
        valid, key=lambda r: (r.subject.name, r.grade, r.units_min)  # type: ignore[union-attr]
    ):
        rng = (
            f"{q.units_min}"
            if q.units_min == q.units_max
            else f"{q.units_min}-{q.units_max}"
        )
        parts.append(f"{q.subject.name} {q.grade} ({rng} יח\"ל)")
    return ", ".join(parts)


class TutorController:
    """Manage tutors, their subject/grade qualifications and constraints."""

    def list_subjects(self) -> list[tuple[int, str]]:
        """Return all subjects as (id, name) for dropdowns."""
        with session_scope() as session:
            rows = session.scalars(select(Subject).order_by(Subject.name)).all()
            return [(s.id, s.name) for s in rows]

    def list_tutors(self) -> list[dict]:
        with session_scope() as session:
            tutors = session.scalars(select(Tutor).order_by(Tutor.name)).all()
            return [
                {
                    "id": tutor.id,
                    "name": tutor.name,
                    "subjects_text": _summarize_quals(tutor.subjects),
                }
                for tutor in tutors
            ]

    def list_tutor_subjects(self, tutor_id: int) -> list[dict]:
        """Return a tutor's subject/grade qualifications as dicts."""
        with session_scope() as session:
            rows = session.scalars(
                select(TutorSubject)
                .where(TutorSubject.tutor_id == tutor_id)
                .order_by(TutorSubject.id)
            ).all()
            return [
                {
                    "id": row.id,
                    "subject_id": row.subject_id,
                    "subject_name": row.subject.name,
                    "grade": row.grade,
                    "units_min": row.units_min,
                    "units_max": row.units_max,
                }
                for row in rows
                if row.subject is not None
            ]

    def add_tutor_subject(
        self,
        tutor_id: int,
        subject_id: int,
        grades: list[str],
        units_min: int,
        units_max: int,
    ) -> int:
        """Qualify a tutor for a subject across one or more grades + units range.

        Returns the number of qualification rows created or updated.
        """
        if not grades:
            raise ValueError("יש לבחור לפחות שכבה אחת")
        for grade in grades:
            if grade not in GRADES:
                raise ValueError(f"שכבה לא חוקית: {grade}")
        if not UNITS_MIN <= units_min <= UNITS_MAX:
            raise ValueError(f'יח"ל חייב להיות בין {UNITS_MIN} ל-{UNITS_MAX}')
        if not UNITS_MIN <= units_max <= UNITS_MAX:
            raise ValueError(f'יח"ל חייב להיות בין {UNITS_MIN} ל-{UNITS_MAX}')
        if units_min > units_max:
            raise ValueError('יח"ל מינימלי גדול מהמקסימלי')

        with session_scope() as session:
            tutor = session.get(Tutor, tutor_id)
            if tutor is None:
                raise ValueError("החונכת לא נמצאה")
            subject = session.get(Subject, subject_id)
            if subject is None:
                raise ValueError("המקצוע לא נמצא")

            affected = 0
            for grade in grades:
                existing = session.scalar(
                    select(TutorSubject).where(
                        TutorSubject.tutor_id == tutor_id,
                        TutorSubject.subject_id == subject_id,
                        TutorSubject.grade == grade,
                    )
                )
                if existing is not None:
                    existing.units_min = units_min
                    existing.units_max = units_max
                else:
                    session.add(
                        TutorSubject(
                            tutor_id=tutor_id,
                            subject_id=subject_id,
                            grade=grade,
                            units_min=units_min,
                            units_max=units_max,
                        )
                    )
                affected += 1
            return affected

    def remove_tutor_subject(self, tutor_subject_id: int) -> None:
        with session_scope() as session:
            row = session.get(TutorSubject, tutor_subject_id)
            if row is not None:
                session.delete(row)

    # ----------------------------------------------------- unavailability
    def get_unavailability(self, tutor_id: int) -> set[tuple[int, int]]:
        """Return the set of (day, hour) cells the tutor cannot teach."""
        with session_scope() as session:
            rows = session.scalars(
                select(TutorUnavailability).where(
                    TutorUnavailability.tutor_id == tutor_id
                )
            ).all()
            return {(r.day, r.hour) for r in rows}

    def set_unavailability(
        self, tutor_id: int, cells: set[tuple[int, int]]
    ) -> None:
        """Replace the tutor's recurring unavailability with the given cells."""
        with session_scope() as session:
            session.query(TutorUnavailability).filter(
                TutorUnavailability.tutor_id == tutor_id
            ).delete()
            for day, hour in sorted(cells):
                session.add(
                    TutorUnavailability(tutor_id=tutor_id, day=day, hour=hour)
                )

    # ------------------------------------------------ global unavailability
    def get_global_unavailability(self) -> set[tuple[int, int]]:
        """Return (day, hour) cells blocked for all tutors (e.g. breaks)."""
        with session_scope() as session:
            rows = session.scalars(select(GlobalUnavailability)).all()
            return {(r.day, r.hour) for r in rows}

    def set_global_unavailability(self, cells: set[tuple[int, int]]) -> None:
        """Replace the school-wide blocked cells with the given set."""
        with session_scope() as session:
            session.query(GlobalUnavailability).delete()
            for day, hour in sorted(cells):
                session.add(GlobalUnavailability(day=day, hour=hour))

    def add_tutor(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("יש להזין שם חונכת")
        with session_scope() as session:
            existing = session.scalar(select(Tutor).where(Tutor.name == name))
            if existing is not None:
                raise ValueError("חונכת בשם זה כבר קיימת")
            tutor = Tutor(name=name)
            session.add(tutor)
            session.flush()
            return tutor.id

    def rename_tutor(self, tutor_id: int, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("יש להזין שם חונכת")
        with session_scope() as session:
            clash = session.scalar(
                select(Tutor).where(Tutor.name == new_name, Tutor.id != tutor_id)
            )
            if clash is not None:
                raise ValueError("חונכת בשם זה כבר קיימת")
            tutor = session.get(Tutor, tutor_id)
            if tutor is not None:
                tutor.name = new_name

    def delete_tutor(self, tutor_id: int) -> None:
        with session_scope() as session:
            tutor = session.get(Tutor, tutor_id)
            if tutor is not None:
                session.delete(tutor)
