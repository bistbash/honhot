"""Global (all-tutors) unavailability: recurring breaks that block everyone.

Unlike :class:`TutorUnavailability`, which blocks a single tutor, a row here
blocks a (day, hour) cell for *every* tutor - useful for school-wide breaks
such as lunch or recess where no tutoring can take place.
"""

from __future__ import annotations

from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GlobalUnavailability(Base):
    """A (day, hour) cell during which no tutor may be scheduled."""

    __tablename__ = "global_unavailability"
    __table_args__ = (
        UniqueConstraint("day", "hour", name="uq_global_unavailable"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<GlobalUnavailability day={self.day} hour={self.hour}>"
