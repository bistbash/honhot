"""View for importing subject workbooks and managing students."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.import_controller import ImportController
from app.services.excel_parser import ExcelImportError, ImportResult
from app.views.student_editor_dialog import StudentEditorDialog


class ImportView(QWidget):
    """Import .xlsx files and manage students of each subject."""

    _STUDENT_HEADERS = ["שם", "שכבה", "כיתה", 'יח"ל', "רמה", "קבוצה", "חונכת מועדפת"]

    def __init__(self) -> None:
        super().__init__()
        self.controller = ImportController()
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        actions = QHBoxLayout()
        import_btn = QPushButton("ייבוא קובץ אקסל")
        import_btn.clicked.connect(self._on_import)
        actions.addWidget(import_btn)

        template_btn = QPushButton("הורדת תבנית לדוגמה")
        template_btn.setProperty("class", "secondary")
        template_btn.clicked.connect(self._on_download_template)
        actions.addWidget(template_btn)

        add_btn = QPushButton("הוספת תלמיד")
        add_btn.clicked.connect(self._on_add_student)
        actions.addWidget(add_btn)

        edit_btn = QPushButton("עריכת תלמיד")
        edit_btn.setProperty("class", "secondary")
        edit_btn.clicked.connect(self._on_edit_student)
        actions.addWidget(edit_btn)

        delete_btn = QPushButton("מחיקת תלמיד")
        delete_btn.setProperty("class", "secondary")
        delete_btn.clicked.connect(self._on_delete_student)
        actions.addWidget(delete_btn)

        actions.addStretch(1)
        actions.addWidget(QLabel("מקצוע:"))
        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(220)
        self.subject_combo.currentIndexChanged.connect(self._reload_students)
        actions.addWidget(self.subject_combo)

        delete_subject_btn = QPushButton("מחיקת מקצוע")
        delete_subject_btn.setProperty("class", "secondary")
        delete_subject_btn.clicked.connect(self._on_delete_subject)
        actions.addWidget(delete_subject_btn)

        layout.addLayout(actions)

        self.table = QTableWidget(0, len(self._STUDENT_HEADERS))
        self.table.setHorizontalHeaderLabels(self._STUDENT_HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.cellDoubleClicked.connect(self._on_edit_student)
        layout.addWidget(self.table, 1)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    # --------------------------------------------------------------- actions
    def _on_import(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "בחירת קובץ אקסל", "", "קבצי אקסל (*.xlsx *.xls)"
        )
        if not file_path:
            return

        try:
            result = self.controller.parse_file(file_path)
        except ExcelImportError as exc:
            QMessageBox.critical(self, "שגיאת ייבוא", str(exc))
            return

        if not result.students and result.has_issues:
            self._show_issues(result, committed=0, subject_name="")
            return

        default_name = self._suggest_subject_name(file_path)
        subject_name, ok = QInputDialog.getText(
            self, "שם מקצוע", "הזן את שם המקצוע עבור קובץ זה:", text=default_name
        )
        if not ok or not subject_name.strip():
            return

        try:
            summary = self.controller.commit_import(subject_name, result)
        except ValueError as exc:
            QMessageBox.warning(self, "שם מקצוע לא תקין", str(exc))
            return

        self.refresh()
        self._select_subject_by_name(summary.subject_name)

        if result.has_issues:
            self._show_issues(
                result, committed=summary.imported, subject_name=summary.subject_name
            )
        else:
            QMessageBox.information(
                self,
                "ייבוא הושלם",
                f"יובאו {summary.imported} תלמידים למקצוע '{summary.subject_name}'.",
            )

    def _on_download_template(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "שמירת תבנית לדוגמה",
            "תבנית_ייבוא_תלמידים.xlsx",
            "קבצי אקסל (*.xlsx)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"
        try:
            self.controller.create_template(file_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "שגיאה", f"לא ניתן ליצור את התבנית:\n{exc}"
            )
            return
        QMessageBox.information(
            self,
            "התבנית נשמרה",
            "נשמרה תבנית לדוגמה עם העמודות הנדרשות:\n"
            'שם תלמיד, כיתה, יח"ל, רמת לימוד.\n\n'
            "מלאו את השורות ושמרו, ואז ייבאו את הקובץ.",
        )

    def _on_add_student(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            QMessageBox.information(self, "אין מקצוע", "יש לבחור מקצוע תחילה.")
            return
        dialog = StudentEditorDialog(self.controller, subject_id, parent=self)
        if dialog.exec() != StudentEditorDialog.DialogCode.Accepted:
            return
        try:
            self.controller.add_student(
                subject_id,
                dialog.name(),
                dialog.grade(),
                dialog.class_number(),
                dialog.units(),
                dialog.study_level(),
                preferred_tutor_id=dialog.preferred_tutor_id(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self._reload_students()

    def _on_edit_student(self, _row: int = -1, _col: int = -1) -> None:
        student_id = self._selected_student_id()
        if student_id is None:
            QMessageBox.information(self, "אין בחירה", "יש לבחור תלמיד לעריכה.")
            return
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        dialog = StudentEditorDialog(
            self.controller, subject_id, student_id=student_id, parent=self
        )
        if dialog.exec() != StudentEditorDialog.DialogCode.Accepted:
            return
        try:
            result = self.controller.update_student(
                student_id,
                dialog.name(),
                dialog.grade(),
                dialog.class_number(),
                dialog.units(),
                dialog.study_level(),
                preferred_tutor_id=dialog.preferred_tutor_id(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        if result.removed_from_group:
            QMessageBox.information(
                self,
                "הוצאה מקבוצה",
                "התלמיד הוצא מהקבוצה בעקבות שינוי שכבה, יח\"ל או רמת לימוד.",
            )
        self._reload_students()

    def _on_delete_student(self) -> None:
        student_id = self._selected_student_id()
        if student_id is None:
            QMessageBox.information(self, "אין בחירה", "יש לבחור תלמיד למחיקה.")
            return
        student = self.controller.get_student(student_id)
        name = student["name"] if student else ""
        confirm = QMessageBox.question(
            self,
            "מחיקת תלמיד",
            f"למחוק את '{name}'? השיבוצים שלו יימחקו.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete_student(student_id)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self._reload_students()

    def _on_delete_subject(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        name = self.subject_combo.currentText()
        confirm = QMessageBox.question(
            self,
            "מחיקת מקצוע",
            f"למחוק את המקצוע '{name}' וכל הנתונים הקשורים אליו?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.controller.delete_subject(subject_id)
        self.refresh()

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _suggest_subject_name(file_path: str) -> str:
        from pathlib import Path

        return Path(file_path).stem

    def _selected_student_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return int(data) if data is not None else None

    def _show_issues(
        self, result: ImportResult, committed: int, subject_name: str
    ) -> None:
        lines = [f"שורה {i.row_number}: {i.message}" for i in result.issues]
        preview = "\n".join(lines[:25])
        if len(lines) > 25:
            preview += f"\n... ועוד {len(lines) - 25} בעיות"

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("ייבוא הושלם עם אזהרות")
        header = (
            f"יובאו {committed} תלמידים"
            + (f" למקצוע '{subject_name}'." if subject_name else ".")
            + f"\nדולגו {len(result.issues)} שורות עם בעיות:"
        )
        box.setText(header)
        box.setDetailedText(preview)
        box.exec()

    def _current_subject_id(self) -> int | None:
        data = self.subject_combo.currentData()
        return int(data) if data is not None else None

    def _select_subject_by_name(self, name: str) -> None:
        index = self.subject_combo.findText(name)
        if index >= 0:
            self.subject_combo.setCurrentIndex(index)

    def _reload_students(self) -> None:
        self.table.setRowCount(0)
        subject_id = self._current_subject_id()
        if subject_id is None:
            self.summary_label.setText("")
            return

        students = self.controller.students_for_subject(subject_id)
        self.table.setRowCount(len(students))
        for row, student in enumerate(students):
            values = [
                student["name"],
                student["grade"],
                str(student["class_number"]),
                str(student["units"]),
                str(student["study_level"]),
                student["group"],
                student["preferred_tutor_name"] or "(ללא)",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, student["id"])
                self.table.setItem(row, col, item)
        self.summary_label.setText(f"סה\"כ {len(students)} תלמידים במקצוע זה.")

    # ----------------------------------------------------------------- public
    def refresh(self) -> None:
        """Reload the subject list and student table from the database."""
        current = self.subject_combo.currentText()
        self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        for subject_id, name in self.controller.list_subjects():
            self.subject_combo.addItem(name, subject_id)
        self.subject_combo.blockSignals(False)

        if current:
            self._select_subject_by_name(current)
        self._reload_students()
