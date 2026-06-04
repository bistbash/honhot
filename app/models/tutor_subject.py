"""Tutor qualification: which subject, grade and units (יח\"ל) a tutor teaches.

A tutor can teach a subject for a specific grade (שכבה) within a units range,
e.g. math for grades י', י"א, י"ב at 3-5 units. Each grade is stored as its own
row so a tutor teaching three grades has three rows for that subject.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.subject import Subject
    from app.models.tutor import Tutor


class TutorSubject(Base):
    """A subject + grade + units range that a tutor is qualified to teach."""

    __tablename__ = "tutor_subjects"
    __table_args__ = (
        UniqueConstraint(
            "tutor_id", "subject_id", "grade", name="uq_tutor_subject_grade"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tutor_id: Mapped[int] = mapped_column(
        ForeignKey("tutors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade: Mapped[str] = mapped_column(String(8), nullable=False)  # שכבה
    units_min: Mapped[int] = mapped_column(Integer, nullable=False)
    units_max: Mapped[int] = mapped_column(Integer, nullable=False)

    tutor: Mapped["Tutor"] = relationship(back_populates="subjects")
    subject: Mapped["Subject"] = relationship(back_populates="tutor_qualifications")

    def covers(self, grade: str, units: int) -> bool:
        """Return True if this qualification matches the given grade and units."""
        return self.grade == grade and self.units_min <= units <= self.units_max

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TutorSubject tutor_id={self.tutor_id} subject_id={self.subject_id} "
            f"grade={self.grade} units={self.units_min}-{self.units_max}>"
        )
