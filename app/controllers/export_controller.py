"""Controller and dialog for exporting the schedule to Excel, PDF or HTML."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QMessageBox,
    QWidget,
)

from app.config import APP_NAME, DAYS, HOURS
from app.database import session_scope
from app.models import EntityType, ScheduleSlot, Student, StudyGroup, Subject, Tutor
from app.services.exporter import TutorSchedule, export_to_excel, export_to_pdf
from app.services.html_schedule_exporter import (
    HtmlSchedulePayload,
    LessonBlock,
    ScheduleSheet,
    build_interactive_html,
    cell_key,
)


class ExportController:
    """Builds export data and drives the export dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.parent = parent

    # --------------------------------------------------------------- data
    def _slot_label(self, slot: ScheduleSlot) -> str:
        if slot.entity_type == EntityType.STUDENT and slot.student:
            return f"{slot.student.display_label}\n{slot.subject.name}"
        if slot.study_group:
            return f"{slot.study_group.name}\n{slot.subject.name}"
        return slot.subject.name

    def build_schedules(self, tutor_id: int | None) -> list[TutorSchedule]:
        """Build per-tutor schedules; ``None`` means the whole system."""
        schedules: list[TutorSchedule] = []
        with session_scope() as session:
            tutor_stmt = select(Tutor).order_by(Tutor.name)
            if tutor_id is not None:
                tutor_stmt = tutor_stmt.where(Tutor.id == tutor_id)
            tutors = session.scalars(tutor_stmt).all()

            for tutor in tutors:
                cells: dict[tuple[int, int], str] = {}
                for slot in tutor.schedule_slots:
                    cells[(slot.day, slot.hour)] = self._slot_label(slot)
                schedules.append(
                    TutorSchedule(tutor_name=tutor.name, cells=cells)
                )
        return schedules

    @staticmethod
    def _student_lesson_label(student: Student) -> str:
        return f"{student.name} · ת.ז. {student.national_id}"

    @staticmethod
    def _lesson_from_slot(slot: ScheduleSlot) -> LessonBlock:
        if slot.entity_type == EntityType.STUDENT and slot.student:
            students = [ExportController._student_lesson_label(slot.student)]
        elif slot.study_group:
            students = [
                ExportController._student_lesson_label(member)
                for member in slot.study_group.members
            ]
        else:
            students = []
        return LessonBlock(
            subject=slot.subject.name,
            tutor=slot.tutor.name,
            students=students,
        )

    def _load_slots(self) -> list[ScheduleSlot]:
        with session_scope() as session:
            return list(
                session.scalars(
                    select(ScheduleSlot)
                    .options(
                        joinedload(ScheduleSlot.tutor),
                        joinedload(ScheduleSlot.subject),
                        joinedload(ScheduleSlot.student),
                        joinedload(ScheduleSlot.study_group).joinedload(
                            StudyGroup.members
                        ),
                    )
                    .order_by(ScheduleSlot.day, ScheduleSlot.hour)
                ).unique()
            )

    @staticmethod
    def _build_tutor_sheets(
        tutors: list[Tutor], slots: list[ScheduleSlot]
    ) -> list[ScheduleSheet]:
        slots_by_tutor: dict[int, list[ScheduleSlot]] = {}
        for slot in slots:
            slots_by_tutor.setdefault(slot.tutor_id, []).append(slot)

        sheets: list[ScheduleSheet] = []
        for tutor in tutors:
            cells: dict[str, list[LessonBlock]] = {}
            for slot in slots_by_tutor.get(tutor.id, []):
                key = cell_key(slot.day, slot.hour)
                cells[key] = [ExportController._lesson_from_slot(slot)]
            sheets.append(
                ScheduleSheet(
                    id=tutor.id,
                    name=tutor.name,
                    kind="tutor",
                    cells=cells,
                )
            )
        return sheets

    @staticmethod
    def _build_subject_sheets(
        subjects: list[Subject], slots: list[ScheduleSlot]
    ) -> list[ScheduleSheet]:
        slots_by_subject: dict[int, list[ScheduleSlot]] = {}
        for slot in slots:
            slots_by_subject.setdefault(slot.subject_id, []).append(slot)

        sheets: list[ScheduleSheet] = []
        for subject in subjects:
            cells: dict[str, list[LessonBlock]] = {}
            for slot in slots_by_subject.get(subject.id, []):
                key = cell_key(slot.day, slot.hour)
                cells.setdefault(key, []).append(
                    ExportController._lesson_from_slot(slot)
                )
            sheets.append(
                ScheduleSheet(
                    id=subject.id,
                    name=subject.name,
                    kind="subject",
                    cells=cells,
                )
            )
        return sheets

    @staticmethod
    def _build_student_sheets(
        students: list[Student], slots: list[ScheduleSlot]
    ) -> list[ScheduleSheet]:
        persons: dict[str, list[Student]] = {}
        for student in students:
            persons.setdefault(student.national_id, []).append(student)

        student_ids_by_nid: dict[str, set[int]] = {
            national_id: {s.id for s in group}
            for national_id, group in persons.items()
        }

        group_members: dict[int, set[int]] = {}
        for slot in slots:
            if slot.study_group_id is None or slot.study_group is None:
                continue
            member_ids = group_members.setdefault(
                slot.study_group_id, set()
            )
            for member in slot.study_group.members:
                member_ids.add(member.id)

        sheets: list[ScheduleSheet] = []
        for national_id, person_students in sorted(
            persons.items(), key=lambda item: item[1][0].name
        ):
            person_student_ids = student_ids_by_nid[national_id]
            cells: dict[str, list[LessonBlock]] = {}
            for slot in slots:
                assigned = (
                    slot.entity_type == EntityType.STUDENT
                    and slot.student_id in person_student_ids
                ) or (
                    slot.study_group_id is not None
                    and bool(
                        person_student_ids
                        & group_members.get(slot.study_group_id, set())
                    )
                )
                if not assigned:
                    continue
                key = cell_key(slot.day, slot.hour)
                cells.setdefault(key, []).append(
                    ExportController._lesson_from_slot(slot)
                )

            representative = min(person_students, key=lambda s: s.id)
            label = (
                f"{representative.name} "
                f"({representative.grade}{representative.class_number}) · "
                f"ת.ז. {national_id}"
            )
            sheets.append(
                ScheduleSheet(
                    id=int(national_id),
                    name=label,
                    kind="student",
                    cells=cells,
                    national_id=national_id,
                )
            )
        return sheets

    def build_html_payload(self) -> HtmlSchedulePayload:
        """Collect all schedule data for the interactive HTML export."""
        slots = self._load_slots()
        with session_scope() as session:
            tutors = session.scalars(select(Tutor).order_by(Tutor.name)).all()
            subjects = session.scalars(select(Subject).order_by(Subject.name)).all()
            students = session.scalars(
                select(Student).order_by(Student.name, Student.grade)
            ).all()

        sheets: list[ScheduleSheet] = []
        sheets.extend(self._build_tutor_sheets(tutors, slots))
        sheets.extend(self._build_subject_sheets(subjects, slots))
        sheets.extend(self._build_student_sheets(students, slots))

        return HtmlSchedulePayload(
            title=APP_NAME,
            days=list(DAYS),
            hours=list(HOURS),
            sheets=sheets,
        )

    def export_html_site(self, path: str | Path) -> Path:
        """Write a self-contained interactive HTML schedule to ``path``."""
        path = Path(path)
        payload = self.build_html_payload()
        path.write_text(build_interactive_html(payload), encoding="utf-8")
        return path

    def list_tutors(self) -> list[tuple[int, str]]:
        with session_scope() as session:
            rows = session.scalars(select(Tutor).order_by(Tutor.name)).all()
            return [(t.id, t.name) for t in rows]

    # --------------------------------------------------------------- dialog
    def open_export_dialog(self) -> None:
        tutors = self.list_tutors()

        dialog = QDialog(self.parent)
        dialog.setWindowTitle("ייצוא מערכת שעות")
        form = QFormLayout(dialog)

        scope_combo = QComboBox()
        scope_combo.addItem("כל המערכת", None)
        for tutor_id, name in tutors:
            scope_combo.addItem(f"חונכת: {name}", tutor_id)
        form.addRow("טווח:", scope_combo)

        format_combo = QComboBox()
        format_combo.addItem("Excel (.xlsx)", "xlsx")
        format_combo.addItem("PDF (.pdf)", "pdf")
        format_combo.addItem("HTML (.html)", "html")
        form.addRow("פורמט:", format_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fmt = format_combo.currentData()
        if fmt == "html":
            self._run_html_export()
            return

        tutor_id = scope_combo.currentData()
        self._run_export(tutor_id, fmt)

    def export_html_dialog(self) -> None:
        """Prompt for a save path and export the full interactive HTML site."""
        self._run_html_export()

    def _run_html_export(self) -> None:
        payload = self.build_html_payload()
        if not payload.sheets:
            QMessageBox.information(
                self.parent, "אין נתונים", "אין נתונים לייצוא HTML."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "שמירת אתר HTML",
            "schedule.html",
            "קובץ HTML (*.html)",
        )
        if not path:
            return
        if not path.lower().endswith(".html"):
            path += ".html"

        try:
            self.export_html_site(path)
        except Exception as exc:  # noqa: BLE001 - report any export failure
            QMessageBox.critical(self.parent, "שגיאת ייצוא", str(exc))
            return

        QMessageBox.information(self.parent, "הייצוא הושלם", f"הקובץ נשמר:\n{path}")

    def _run_export(self, tutor_id: int | None, fmt: str) -> None:
        schedules = self.build_schedules(tutor_id)
        if not schedules:
            QMessageBox.information(self.parent, "אין נתונים", "אין חונכות לייצוא.")
            return

        if fmt == "xlsx":
            file_filter = "קובץ אקסל (*.xlsx)"
            default = "schedule.xlsx"
        else:
            file_filter = "קובץ PDF (*.pdf)"
            default = "schedule.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self.parent, "שמירת קובץ", default, file_filter
        )
        if not path:
            return

        title = APP_NAME
        try:
            if fmt == "xlsx":
                export_to_excel(path, schedules, title)
            else:
                export_to_pdf(path, schedules, title)
        except Exception as exc:  # noqa: BLE001 - report any export failure
            QMessageBox.critical(self.parent, "שגיאת ייצוא", str(exc))
            return

        QMessageBox.information(self.parent, "הייצוא הושלם", f"הקובץ נשמר:\n{path}")
