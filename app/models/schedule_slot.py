"""ScheduleSlot model: a tutor's assignment at a given day/hour."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.study_group import StudyGroup
    from app.models.subject import Subject
    from app.models.tutor import Tutor


class EntityType(str, Enum):
    """Type of entity assigned to a schedule slot."""

    STUDENT = "student"
    GROUP = "group"


class ScheduleSlot(Base):
    """An assignment of a student or study group to a tutor at day/hour."""

    __tablename__ = "schedule_slots"
    __table_args__ = (
        UniqueConstraint("tutor_id", "day", "hour", name="uq_tutor_day_hour"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tutor_id: Mapped[int] = mapped_column(
        ForeignKey("tutors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, native_enum=False, length=16), nullable=False
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    study_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_groups.id", ondelete="CASCADE"), nullable=True, index=True
    )

    tutor: Mapped["Tutor"] = relationship(back_populates="schedule_slots")
    subject: Mapped["Subject"] = relationship(back_populates="schedule_slots")
    student: Mapped["Student | None"] = relationship()
    study_group: Mapped["StudyGroup | None"] = relationship()

    @property
    def entity_key(self) -> tuple[str, int]:
        """Return a stable (type, id) key identifying the assigned entity."""
        if self.entity_type == EntityType.STUDENT:
            return (EntityType.STUDENT.value, int(self.student_id or 0))
        return (EntityType.GROUP.value, int(self.study_group_id or 0))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<ScheduleSlot tutor={self.tutor_id} day={self.day} "
            f"hour={self.hour} {self.entity_type.value}>"
        )
