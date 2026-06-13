"""Controller for the interactive timetable: assignment and validation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.config import DAYS, HOUR_MAX, HOUR_MIN, HOURS
from app.database import session_scope
from app.models import (
    EntityType,
    GlobalUnavailability,
    ScheduleSlot,
    Student,
    StudyGroup,
    Subject,
    SubjectTimeWindow,
    Tutor,
    TutorSubject,
    TutorUnavailability,
)
from app.services.auto_scheduler import (
    EntityCandidate,
    TutorState,
    plan_assignments,
)


@dataclass
class EntityInfo:
    """A schedulable entity (a lone student or a study group)."""

    entity_type: str  # "student" | "group"
    entity_id: int
    label: str
    subject_id: int
    subject_name: str
    scheduled_count: int
    required_hours: int | None
    preferred_tutor_name: str = ""
    grade: str = ""
    units: int = 0
    assignable: bool = True


@dataclass
class SlotInfo:
    """A populated timetable cell for display."""

    slot_id: int
    day: int
    hour: int
    entity_type: str
    entity_id: int
    label: str
    subject_name: str


@dataclass
class AssignResult:
    """Outcome of attempting to assign an entity to a slot."""

    ok: bool
    message: str


@dataclass
class AutoAssignSummary:
    """Outcome of an automatic-assignment run."""

    assigned: int
    unassigned_labels: list[str]
    tutor_loads: list[tuple[str, int]]  # (tutor_name, hours) sorted by name


class ScheduleController:
    """Coordinates timetable reads and validated assignments."""

    # --------------------------------------------------------------- reads
    def list_tutors(self) -> list[tuple[int, str]]:
        with session_scope() as session:
            rows = session.scalars(select(Tutor).order_by(Tutor.name)).all()
            return [(t.id, t.name) for t in rows]

    def schedulable_entities(self, tutor_id: int | None = None) -> list[EntityInfo]:
        """Return lone students (not in a group) and all study groups.

        When ``tutor_id`` is given, each entity's ``assignable`` flag reflects
        whether that tutor is qualified to teach it.
        """
        entities: list[EntityInfo] = []
        with session_scope() as session:
            slot_counts = self._entity_slot_counts(session)

            lone_students = session.scalars(
                select(Student).where(Student.study_group_id.is_(None))
            ).all()
            for student in lone_students:
                assignable = True
                if tutor_id is not None:
                    assignable = self._tutor_qualifies(
                        session,
                        tutor_id,
                        student.subject_id,
                        student.grade,
                        student.units,
                    )
                entities.append(
                    EntityInfo(
                        entity_type=EntityType.STUDENT.value,
                        entity_id=student.id,
                        label=student.display_label,
                        subject_id=student.subject_id,
                        subject_name=student.subject.name,
                        scheduled_count=slot_counts.get(
                            (EntityType.STUDENT.value, student.id), 0
                        ),
                        required_hours=student.subject.weekly_hours,
                        preferred_tutor_name=(
                            student.preferred_tutor.name
                            if student.preferred_tutor
                            else ""
                        ),
                        grade=student.grade,
                        units=student.units,
                        assignable=assignable,
                    )
                )

            groups = session.scalars(select(StudyGroup)).all()
            for group in groups:
                assignable = True
                if tutor_id is not None:
                    assignable = self._tutor_qualifies(
                        session,
                        tutor_id,
                        group.subject_id,
                        group.grade,
                        group.units,
                    )
                entities.append(
                    EntityInfo(
                        entity_type=EntityType.GROUP.value,
                        entity_id=group.id,
                        label=group.display_label,
                        subject_id=group.subject_id,
                        subject_name=group.subject.name,
                        scheduled_count=slot_counts.get(
                            (EntityType.GROUP.value, group.id), 0
                        ),
                        required_hours=group.subject.weekly_hours,
                        preferred_tutor_name=(
                            group.preferred_tutor.name
                            if group.preferred_tutor
                            else ""
                        ),
                        grade=group.grade,
                        units=group.units,
                        assignable=assignable,
                    )
                )

        entities.sort(key=lambda e: (e.subject_name, e.label))
        return entities

    def slots_for_tutor(self, tutor_id: int) -> dict[tuple[int, int], SlotInfo]:
        """Return {(day, hour): SlotInfo} for one tutor."""
        result: dict[tuple[int, int], SlotInfo] = {}
        with session_scope() as session:
            slots = session.scalars(
                select(ScheduleSlot).where(ScheduleSlot.tutor_id == tutor_id)
            ).all()
            for slot in slots:
                result[(slot.day, slot.hour)] = SlotInfo(
                    slot_id=slot.id,
                    day=slot.day,
                    hour=slot.hour,
                    entity_type=slot.entity_type.value,
                    entity_id=(slot.student_id or slot.study_group_id or 0),
                    label=self._slot_label(slot),
                    subject_name=slot.subject.name,
                )
        return result

    def reserved_cells_for_entity(
        self, entity_type: str, entity_id: int
    ) -> set[tuple[int, int]] | None:
        """Return reserved (day, hour) cells for the entity's subject.

        Returns ``None`` when the subject is unrestricted (no windows defined).
        """
        with session_scope() as session:
            subject_id = self._entity_subject_id(session, entity_type, entity_id)
            if subject_id is None:
                return None
            windows = session.scalars(
                select(SubjectTimeWindow).where(
                    SubjectTimeWindow.subject_id == subject_id
                )
            ).all()
            if not windows:
                return None
            return {(w.day, w.hour) for w in windows}

    # --------------------------------------------------------------- writes
    def try_assign(
        self,
        tutor_id: int,
        day: int,
        hour: int,
        entity_type: str,
        entity_id: int,
    ) -> AssignResult:
        """Validate and persist an assignment. Returns an :class:`AssignResult`."""
        if not (0 <= day < len(DAYS)) or not (HOUR_MIN <= hour <= HOUR_MAX):
            return AssignResult(False, "תא לא חוקי במערכת.")

        with session_scope() as session:
            tutor = session.get(Tutor, tutor_id)
            if tutor is None:
                return AssignResult(False, "החונכת לא נמצאה.")

            # Rule: globally blocked slot (e.g. a break) - no tutor may teach.
            global_block = session.scalar(
                select(GlobalUnavailability).where(
                    GlobalUnavailability.day == day,
                    GlobalUnavailability.hour == hour,
                )
            )
            if global_block is not None:
                return AssignResult(
                    False,
                    f"{DAYS[day]} שעה {hour} חסומה לכלל החונכות (אילוץ כללי).",
                )

            # Rule: tutor must be available at this (day, hour).
            blocked = session.scalar(
                select(TutorUnavailability).where(
                    TutorUnavailability.tutor_id == tutor_id,
                    TutorUnavailability.day == day,
                    TutorUnavailability.hour == hour,
                )
            )
            if blocked is not None:
                return AssignResult(
                    False,
                    f"{tutor.name} אינה זמינה ב{DAYS[day]} שעה {hour} (אילוץ קבוע).",
                )

            subject_id = self._entity_subject_id(session, entity_type, entity_id)
            if subject_id is None:
                return AssignResult(False, "הישות לשיבוץ לא נמצאה.")

            units = self._entity_units(session, entity_type, entity_id)
            grade = self._entity_grade(session, entity_type, entity_id)
            if units is None or grade is None:
                return AssignResult(False, "לא ניתן לזהות את פרטי הישות.")

            # Rule 0: tutor must be qualified for this subject + grade + units.
            qual_rows = session.scalars(
                select(TutorSubject).where(
                    TutorSubject.tutor_id == tutor_id,
                    TutorSubject.subject_id == subject_id,
                )
            ).all()
            if not any(q.covers(grade, units) for q in qual_rows):
                subject = session.get(Subject, subject_id)
                subject_name = subject.name if subject else "המקצוע"
                if qual_rows:
                    return AssignResult(
                        False,
                        f"החונכת לא מלמדת {subject_name} לשכבה {grade} "
                        f"ב-{units} יח\"ל.",
                    )
                return AssignResult(
                    False,
                    f"החונכת לא מוגדרת ל{subject_name}. "
                    "יש להוסיף מקצוע/שכבה בלשונית חונכות.",
                )

            # Rule 1: target slot must be free for this tutor.
            occupied = session.scalar(
                select(ScheduleSlot).where(
                    ScheduleSlot.tutor_id == tutor_id,
                    ScheduleSlot.day == day,
                    ScheduleSlot.hour == hour,
                )
            )
            if occupied is not None:
                return AssignResult(
                    False, f"המשבצת תפוסה אצל {tutor.name} ({DAYS[day]} שעה {hour})."
                )

            # Rule 2: entity must not be booked elsewhere at the same day+hour.
            clash_stmt = select(ScheduleSlot).where(
                ScheduleSlot.day == day, ScheduleSlot.hour == hour
            )
            if entity_type == EntityType.STUDENT.value:
                clash_stmt = clash_stmt.where(ScheduleSlot.student_id == entity_id)
            else:
                clash_stmt = clash_stmt.where(
                    ScheduleSlot.study_group_id == entity_id
                )
            if session.scalar(clash_stmt) is not None:
                return AssignResult(
                    False,
                    f"הישות כבר משובצת ב{DAYS[day]} שעה {hour} אצל חונכת אחרת.",
                )

            # Rule 3: subject reserved windows.
            windows = session.scalars(
                select(SubjectTimeWindow).where(
                    SubjectTimeWindow.subject_id == subject_id
                )
            ).all()
            if windows and (day, hour) not in {(w.day, w.hour) for w in windows}:
                return AssignResult(
                    False,
                    "המקצוע משוריין לזמנים אחרים בלבד; לא ניתן לשבץ בתא זה.",
                )

            slot = ScheduleSlot(
                tutor_id=tutor_id,
                day=day,
                hour=hour,
                subject_id=subject_id,
                entity_type=EntityType(entity_type),
                student_id=entity_id
                if entity_type == EntityType.STUDENT.value
                else None,
                study_group_id=entity_id
                if entity_type == EntityType.GROUP.value
                else None,
            )
            session.add(slot)

        return AssignResult(True, "השיבוץ נוסף בהצלחה.")

    def move_assignment(
        self,
        tutor_id: int,
        src_day: int,
        src_hour: int,
        dst_day: int,
        dst_hour: int,
    ) -> AssignResult:
        """Move a lesson from one cell to another, re-validating the target.

        If the target is invalid the original lesson is restored unchanged.
        """
        if (src_day, src_hour) == (dst_day, dst_hour):
            return AssignResult(True, "")

        with session_scope() as session:
            slot = session.scalar(
                select(ScheduleSlot).where(
                    ScheduleSlot.tutor_id == tutor_id,
                    ScheduleSlot.day == src_day,
                    ScheduleSlot.hour == src_hour,
                )
            )
            if slot is None:
                return AssignResult(False, "אין שיעור במשבצת המקור.")
            entity_type = slot.entity_type.value
            entity_id = slot.student_id or slot.study_group_id or 0

        self.unassign(tutor_id, src_day, src_hour)
        result = self.try_assign(
            tutor_id, dst_day, dst_hour, entity_type, entity_id
        )
        if not result.ok:
            # Restore the original lesson; it was valid before the move.
            self.try_assign(tutor_id, src_day, src_hour, entity_type, entity_id)
        return result

    def unassign(self, tutor_id: int, day: int, hour: int) -> None:
        """Remove the assignment in a tutor's slot, if any."""
        with session_scope() as session:
            slot = session.scalar(
                select(ScheduleSlot).where(
                    ScheduleSlot.tutor_id == tutor_id,
                    ScheduleSlot.day == day,
                    ScheduleSlot.hour == hour,
                )
            )
            if slot is not None:
                session.delete(slot)

    def unavailable_cells_for_tutor(
        self, tutor_id: int
    ) -> set[tuple[int, int]]:
        """Return the (day, hour) cells a tutor is permanently unavailable in."""
        with session_scope() as session:
            rows = session.scalars(
                select(TutorUnavailability).where(
                    TutorUnavailability.tutor_id == tutor_id
                )
            ).all()
            return {(r.day, r.hour) for r in rows}

    def global_unavailable_cells(self) -> set[tuple[int, int]]:
        """Return (day, hour) cells blocked for all tutors (school-wide breaks)."""
        with session_scope() as session:
            rows = session.scalars(select(GlobalUnavailability)).all()
            return {(r.day, r.hour) for r in rows}

    # ------------------------------------------------------------ auto-assign
    def auto_assign(self, clear_existing: bool) -> AutoAssignSummary:
        """Automatically assign entities to tutors with balanced workloads.

        Each entity whose subject has ``weekly_hours`` set needs that many
        tutoring hours per week. Subjects without weekly hours are skipped
        (manual assignment only).

        Args:
            clear_existing: when ``True`` the current schedule is wiped and a
                fresh balanced plan is built; when ``False`` only the missing
                hours of partially/unscheduled entities are filled on top of
                the existing schedule.
        """
        all_cells = {(d, h) for d in range(len(DAYS)) for h in HOURS}

        with session_scope() as session:
            if clear_existing:
                session.query(ScheduleSlot).delete()
                session.flush()

            # School-wide blocked cells (breaks) apply to every tutor.
            global_blocked = {
                (r.day, r.hour)
                for r in session.scalars(select(GlobalUnavailability)).all()
            }
            base_cells = all_cells - global_blocked

            # Subject reserved windows: {subject_id: {(day, hour), ...}}.
            subject_windows: dict[int, set[tuple[int, int]]] = {}
            for window in session.scalars(select(SubjectTimeWindow)).all():
                subject_windows.setdefault(window.subject_id, set()).add(
                    (window.day, window.hour)
                )

            # Existing occupancy and cross-subject person state.
            occupied_by_tutor: dict[int, set[tuple[int, int]]] = {}
            scheduled_counts: dict[tuple[str, int], int] = {}
            person_occupied: dict[str, set[tuple[int, int]]] = {}
            person_tutor: dict[str, int] = {}
            entity_tutor_counts: dict[tuple[str, int], dict[int, int]] = {}
            students_by_id = {
                s.id: s for s in session.scalars(select(Student)).all()
            }
            for slot in session.scalars(select(ScheduleSlot)).all():
                occupied_by_tutor.setdefault(slot.tutor_id, set()).add(
                    (slot.day, slot.hour)
                )
                scheduled_counts[slot.entity_key] = (
                    scheduled_counts.get(slot.entity_key, 0) + 1
                )
                entity_tutor_counts.setdefault(slot.entity_key, {})[
                    slot.tutor_id
                ] = entity_tutor_counts.get(slot.entity_key, {}).get(
                    slot.tutor_id, 0
                ) + 1
                person_key = self._slot_person_key(slot, students_by_id)
                if person_key is not None:
                    person_occupied.setdefault(person_key, set()).add(
                        (slot.day, slot.hour)
                    )
                    person_tutor[person_key] = slot.tutor_id

            # Build tutor states for qualified tutors. Qualifications expand a
            # (subject, grade, units range) row into discrete (subject, grade,
            # units) keys, so range membership becomes a simple set lookup.
            tutor_states: list[TutorState] = []
            for tutor in session.scalars(select(Tutor).order_by(Tutor.name)).all():
                quals: set[tuple[int, str, int]] = set()
                for q in tutor.subjects:
                    for units in range(q.units_min, q.units_max + 1):
                        quals.add((q.subject_id, q.grade, units))
                if not quals:
                    continue
                unavailable = {(u.day, u.hour) for u in tutor.unavailabilities}
                occupied = occupied_by_tutor.get(tutor.id, set())
                free = base_cells - unavailable - occupied
                tutor_states.append(
                    TutorState(
                        tutor_id=tutor.id,
                        name=tutor.name,
                        qualifications=quals,
                        free_cells=free,
                        occupied_cells=set(occupied),
                        load=len(occupied),
                    )
                )

            # Build entities still needing hours (required minus already done).
            entities: list[EntityCandidate] = []

            def _remaining(key: tuple[str, int], weekly: int | None) -> int:
                if weekly is None:
                    return 0
                return max(0, weekly - scheduled_counts.get(key, 0))

            def _preferred_tutor(entity_key: tuple[str, int]) -> int | None:
                counts = entity_tutor_counts.get(entity_key)
                if not counts:
                    return None
                return max(counts, key=lambda tid: (counts[tid], -tid))

            def _resolve_preferred(
                explicit: int | None, entity_key: tuple[str, int]
            ) -> int | None:
                if explicit is not None:
                    return explicit
                return _preferred_tutor(entity_key)

            lone_students = session.scalars(
                select(Student).where(Student.study_group_id.is_(None))
            ).all()
            for student in lone_students:
                weekly = student.subject.weekly_hours
                if weekly is None:
                    continue
                key = (EntityType.STUDENT.value, student.id)
                remaining = _remaining(key, weekly)
                if remaining <= 0:
                    continue
                entities.append(
                    EntityCandidate(
                        entity_type=EntityType.STUDENT.value,
                        entity_id=student.id,
                        subject_id=student.subject_id,
                        grade=student.grade,
                        units=student.units,
                        label=student.display_label,
                        person_key=self._student_person_key(student),
                        required_hours=remaining,
                        preferred_tutor_id=_resolve_preferred(
                            student.preferred_tutor_id, key
                        ),
                    )
                )
            for group in session.scalars(select(StudyGroup)).all():
                weekly = group.subject.weekly_hours
                if weekly is None:
                    continue
                key = (EntityType.GROUP.value, group.id)
                remaining = _remaining(key, weekly)
                if remaining <= 0:
                    continue
                entities.append(
                    EntityCandidate(
                        entity_type=EntityType.GROUP.value,
                        entity_id=group.id,
                        subject_id=group.subject_id,
                        grade=group.grade,
                        units=group.units,
                        label=group.name,
                        person_key=self._group_person_key(group.id),
                        required_hours=remaining,
                        preferred_tutor_id=_resolve_preferred(
                            group.preferred_tutor_id, key
                        ),
                    )
                )

            plan = plan_assignments(
                entities,
                tutor_states,
                subject_windows,
                person_occupied=person_occupied,
                person_tutor=person_tutor,
            )

            for assignment in plan.assignments:
                session.add(
                    ScheduleSlot(
                        tutor_id=assignment.tutor_id,
                        day=assignment.day,
                        hour=assignment.hour,
                        subject_id=assignment.subject_id,
                        entity_type=EntityType(assignment.entity_type),
                        student_id=assignment.entity_id
                        if assignment.entity_type == EntityType.STUDENT.value
                        else None,
                        study_group_id=assignment.entity_id
                        if assignment.entity_type == EntityType.GROUP.value
                        else None,
                    )
                )

            tutor_loads = sorted(
                ((t.name, t.load) for t in tutor_states), key=lambda x: x[0]
            )

        unassigned_labels = [
            f"{s.entity.label} (חסרות {s.missing_hours} שעות)"
            for s in plan.shortfalls
        ]
        return AutoAssignSummary(
            assigned=plan.assigned_count,
            unassigned_labels=unassigned_labels,
            tutor_loads=tutor_loads,
        )

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _student_person_key(student: Student) -> str:
        return f"{student.name}|{student.grade}|{student.class_number}"

    @staticmethod
    def _group_person_key(group_id: int) -> str:
        return f"group:{group_id}"

    @staticmethod
    def _slot_person_key(
        slot: ScheduleSlot, students_by_id: dict[int, Student]
    ) -> str | None:
        if slot.student_id is not None:
            student = students_by_id.get(slot.student_id)
            if student is not None:
                return ScheduleController._student_person_key(student)
        if slot.study_group_id is not None:
            return ScheduleController._group_person_key(slot.study_group_id)
        return None

    @staticmethod
    def _entity_subject_id(session, entity_type: str, entity_id: int) -> int | None:
        if entity_type == EntityType.STUDENT.value:
            student = session.get(Student, entity_id)
            return student.subject_id if student else None
        group = session.get(StudyGroup, entity_id)
        return group.subject_id if group else None

    @staticmethod
    def _entity_units(session, entity_type: str, entity_id: int) -> int | None:
        if entity_type == EntityType.STUDENT.value:
            student = session.get(Student, entity_id)
            return student.units if student else None
        group = session.get(StudyGroup, entity_id)
        return group.units if group else None

    @staticmethod
    def _entity_grade(session, entity_type: str, entity_id: int) -> str | None:
        if entity_type == EntityType.STUDENT.value:
            student = session.get(Student, entity_id)
            return student.grade if student else None
        group = session.get(StudyGroup, entity_id)
        return group.grade if group else None

    @staticmethod
    def _slot_label(slot: ScheduleSlot) -> str:
        if slot.entity_type == EntityType.STUDENT.value and slot.student:
            return f"{slot.student.display_label}\n{slot.subject.name}"
        if slot.study_group:
            return f"{slot.study_group.name}\n{slot.subject.name}"
        return slot.subject.name

    @staticmethod
    def _tutor_qualifies(
        session, tutor_id: int, subject_id: int, grade: str, units: int
    ) -> bool:
        qual_rows = session.scalars(
            select(TutorSubject).where(
                TutorSubject.tutor_id == tutor_id,
                TutorSubject.subject_id == subject_id,
            )
        ).all()
        return any(q.covers(grade, units) for q in qual_rows)

    @staticmethod
    def _entity_slot_counts(session) -> dict[tuple[str, int], int]:
        counts: dict[tuple[str, int], int] = {}
        for slot in session.scalars(select(ScheduleSlot)).all():
            counts[slot.entity_key] = counts.get(slot.entity_key, 0) + 1
        return counts
