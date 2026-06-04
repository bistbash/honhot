"""Controller and dialog for exporting the schedule to Excel or PDF."""

from __future__ import annotations

from sqlalchemy import select
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QMessageBox,
    QWidget,
)

from app.config import APP_NAME
from app.database import session_scope
from app.models import EntityType, ScheduleSlot, Tutor
from app.services.exporter import TutorSchedule, export_to_excel, export_to_pdf


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

        tutor_id = scope_combo.currentData()
        fmt = format_combo.currentData()
        self._run_export(tutor_id, fmt)

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
