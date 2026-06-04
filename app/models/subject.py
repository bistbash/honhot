"""Subject model (מקצוע) and its reserved time windows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.schedule_slot import ScheduleSlot
    from app.models.student import Student
    from app.models.study_group import StudyGroup
    from app.models.subject_time_window import SubjectTimeWindow
    from app.models.tutor_subject import TutorSubject


class Subject(Base):
    """A school subject (מקצוע). One subject per imported Excel file."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Weekly tutoring hours each student needs in this subject.
    weekly_hours: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )

    students: Mapped[list["Student"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    study_groups: Mapped[list["StudyGroup"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    time_windows: Mapped[list["SubjectTimeWindow"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    schedule_slots: Mapped[list["ScheduleSlot"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    tutor_qualifications: Mapped[list["TutorSubject"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Subject id={self.id} name={self.name!r}>"
