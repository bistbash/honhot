"""Tutor model (חונכת)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.schedule_slot import ScheduleSlot
    from app.models.tutor_subject import TutorSubject
    from app.models.tutor_unavailability import TutorUnavailability


class Tutor(Base):
    """A tutor/mentor. Inactive tutors cannot receive new assignments."""

    __tablename__ = "tutors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    schedule_slots: Mapped[list["ScheduleSlot"]] = relationship(
        back_populates="tutor", cascade="all, delete-orphan"
    )
    subjects: Mapped[list["TutorSubject"]] = relationship(
        back_populates="tutor", cascade="all, delete-orphan"
    )
    unavailabilities: Mapped[list["TutorUnavailability"]] = relationship(
        back_populates="tutor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Tutor id={self.id} name={self.name!r} active={self.is_active}>"
