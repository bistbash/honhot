"""Aggregates system-wide statistics for the overview dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select

from app.database import session_scope
from app.models import (
    EntityType,
    ScheduleSlot,
    Student,
    StudyGroup,
    Subject,
    Tutor,
)


@dataclass
class TutorLoad:
    """A tutor's weekly teaching load and whether they have qualifications."""

    name: str
    hours: int
    qualified: bool


@dataclass
class PendingEntity:
    """A schedulable entity that still needs hours assigned."""

    label: str
    subject_name: str
    scheduled: int
    required: int

    @property
    def missing(self) -> int:
        return max(0, self.required - self.scheduled)


@dataclass
class Overview:
    """A snapshot of the whole system for the dashboard."""

    students_total: int = 0
    lone_students: int = 0
    grouped_students: int = 0
    groups_total: int = 0
    tutors_total: int = 0
    tutors_unqualified: int = 0
    subjects_total: int = 0
    required_hours: int = 0
    assigned_hours: int = 0
    tutor_loads: list[TutorLoad] = field(default_factory=list)
    pending: list[PendingEntity] = field(default_factory=list)

    @property
    def coverage_pct(self) -> int:
        if self.required_hours <= 0:
            return 0
        return round(100 * min(self.assigned_hours, self.required_hours)
                     / self.required_hours)

    @property
    def min_load(self) -> int:
        loads = [t.hours for t in self.tutor_loads if t.qualified]
        return min(loads) if loads else 0

    @property
    def max_load(self) -> int:
        loads = [t.hours for t in self.tutor_loads if t.qualified]
        return max(loads) if loads else 0

    @property
    def balance_spread(self) -> int:
        """Difference between the busiest and quietest qualified tutor."""
        return self.max_load - self.min_load


class DashboardController:
    """Produces a single :class:`Overview` snapshot for the dashboard view."""

    def get_overview(self) -> Overview:
        ov = Overview()
        with session_scope() as session:
            ov.students_total = session.scalar(
                select(func.count()).select_from(Student)
            ) or 0
            ov.lone_students = session.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.study_group_id.is_(None))
            ) or 0
            ov.grouped_students = ov.students_total - ov.lone_students
            ov.groups_total = session.scalar(
                select(func.count()).select_from(StudyGroup)
            ) or 0
            ov.subjects_total = session.scalar(
                select(func.count()).select_from(Subject)
            ) or 0
            ov.assigned_hours = session.scalar(
                select(func.count()).select_from(ScheduleSlot)
            ) or 0

            # Per-tutor load and qualification flag.
            slot_counts: dict[int, int] = {}
            for tutor_id, count in session.execute(
                select(ScheduleSlot.tutor_id, func.count())
                .group_by(ScheduleSlot.tutor_id)
            ).all():
                slot_counts[tutor_id] = count

            tutors = session.scalars(select(Tutor).order_by(Tutor.name)).all()
            ov.tutors_total = len(tutors)
            for tutor in tutors:
                qualified = len(tutor.subjects) > 0
                if not qualified:
                    ov.tutors_unqualified += 1
                ov.tutor_loads.append(
                    TutorLoad(
                        name=tutor.name,
                        hours=slot_counts.get(tutor.id, 0),
                        qualified=qualified,
                    )
                )

            # Required hours + pending (under-scheduled) entities.
            entity_slot_counts: dict[tuple[str, int], int] = {}
            for slot in session.scalars(select(ScheduleSlot)).all():
                entity_slot_counts[slot.entity_key] = (
                    entity_slot_counts.get(slot.entity_key, 0) + 1
                )

            lone = session.scalars(
                select(Student).where(Student.study_group_id.is_(None))
            ).all()
            for student in lone:
                required = student.subject.weekly_hours
                if required is None:
                    continue
                ov.required_hours += required
                scheduled = entity_slot_counts.get(
                    (EntityType.STUDENT.value, student.id), 0
                )
                if scheduled < required:
                    ov.pending.append(
                        PendingEntity(
                            label=student.display_label,
                            subject_name=student.subject.name,
                            scheduled=scheduled,
                            required=required,
                        )
                    )

            for group in session.scalars(select(StudyGroup)).all():
                required = group.subject.weekly_hours
                if required is None:
                    continue
                ov.required_hours += required
                scheduled = entity_slot_counts.get(
                    (EntityType.GROUP.value, group.id), 0
                )
                if scheduled < required:
                    ov.pending.append(
                        PendingEntity(
                            label=group.name,
                            subject_name=group.subject.name,
                            scheduled=scheduled,
                            required=required,
                        )
                    )

        ov.pending.sort(key=lambda p: (-p.missing, p.subject_name, p.label))
        ov.tutor_loads.sort(key=lambda t: (not t.qualified, -t.hours, t.name))
        return ov
