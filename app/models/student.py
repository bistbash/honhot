"""Student model (תלמיד).

Each imported Excel row becomes one Student record. ``units`` (יח"ל) and
``study_level`` (רמת לימוד) are per-subject attributes, which is why a single
person appearing in two subjects is represented by two Student rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.study_group import StudyGroup
    from app.models.subject import Subject
    from app.models.tutor import Tutor


class Student(Base):
    """A student needing tutoring in a specific subject."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    national_id: Mapped[str] = mapped_column(String(9), nullable=False, index=True)
    grade: Mapped[str] = mapped_column(String(8), nullable=False)  # שכבה
    class_number: Mapped[int] = mapped_column(Integer, nullable=False)  # מספר כיתה
    units: Mapped[int] = mapped_column(Integer, nullable=False)  # יח"ל (1-5)
    study_level: Mapped[int] = mapped_column(Integer, nullable=False)  # רמה (1-5)

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    study_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    preferred_tutor_id: Mapped[int | None] = mapped_column(
        ForeignKey("tutors.id", ondelete="SET NULL"), nullable=True, index=True
    )

    subject: Mapped["Subject"] = relationship(back_populates="students")
    study_group: Mapped["StudyGroup | None"] = relationship(back_populates="members")
    preferred_tutor: Mapped["Tutor | None"] = relationship(
        foreign_keys=[preferred_tutor_id]
    )

    @property
    def display_label(self) -> str:
        """Human-readable label used in lists and the timetable grid."""
        return (
            f"{self.name} ({self.grade}{self.class_number}) · ת.ז. {self.national_id}"
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Student id={self.id} name={self.name!r} grade={self.grade} "
            f"units={self.units} level={self.study_level}>"
        )
