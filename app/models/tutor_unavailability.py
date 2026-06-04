"""Recurring tutor unavailability: a (day, hour) the tutor cannot teach.

This is distinct from ``Tutor.is_active`` (a full deactivation). An
unavailability marks a specific weekly slot in which the tutor may not be
assigned (e.g. every Tuesday at hours 1-2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tutor import Tutor


class TutorUnavailability(Base):
    """A weekly (day, hour) cell in which a tutor cannot teach."""

    __tablename__ = "tutor_unavailability"
    __table_args__ = (
        UniqueConstraint("tutor_id", "day", "hour", name="uq_tutor_unavailable"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tutor_id: Mapped[int] = mapped_column(
        ForeignKey("tutors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)

    tutor: Mapped["Tutor"] = relationship(back_populates="unavailabilities")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TutorUnavailability tutor_id={self.tutor_id} "
            f"day={self.day} hour={self.hour}>"
        )
