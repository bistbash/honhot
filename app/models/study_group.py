"""StudyGroup model (קבוצת לימוד).

A dynamic grouping of students who share the exact same subject, grade, units
and study level. Once students are merged into a group, the group becomes the
schedulable entity instead of the individual students.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.subject import Subject


class StudyGroup(Base):
    """A group of students sharing subject, grade, units and study level."""

    __tablename__ = "study_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[str] = mapped_column(String(8), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    study_level: Mapped[int] = mapped_column(Integer, nullable=False)

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    subject: Mapped["Subject"] = relationship(back_populates="study_groups")
    members: Mapped[list["Student"]] = relationship(back_populates="study_group")

    @property
    def display_label(self) -> str:
        """Human-readable label used in lists and the timetable grid."""
        return f"{self.name} [{len(self.members)} תלמידים]"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<StudyGroup id={self.id} name={self.name!r}>"
