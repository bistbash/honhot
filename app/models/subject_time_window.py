"""Reserved time window for a subject (e.g. math only on Tuesday hours 3-5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.subject import Subject


class SubjectTimeWindow(Base):
    """A single (day, hour) cell during which a subject may be scheduled.

    If a subject has any time windows, it may ONLY be scheduled inside them.
    A subject with no windows has no time restriction.
    """

    __tablename__ = "subject_time_windows"
    __table_args__ = (
        UniqueConstraint("subject_id", "day", "hour", name="uq_subject_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="time_windows")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<SubjectTimeWindow subject_id={self.subject_id} "
            f"day={self.day} hour={self.hour}>"
        )
