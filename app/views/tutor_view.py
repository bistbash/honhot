"""View for managing tutors: add, rename, qualifications and constraints."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import GRADES, UNITS_MAX, UNITS_MIN
from app.controllers.tutor_controller import TutorController
from app.views.availability_dialog import AvailabilityGridDialog


class TutorView(QWidget):
    """Manage the roster of tutors, their qualifications and constraints."""

    _HEADERS = ["שם החונכת", "מקצועות ושכבות"]

    def __init__(self) -> None:
        super().__init__()
        self.controller = TutorController()
        self._grade_checks: dict[str, QCheckBox] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("חונכת חדשה:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("שם החונכת")
        self.name_edit.returnPressed.connect(self._on_add)
        add_row.addWidget(self.name_edit, 1)
        add_btn = QPushButton("הוספה")
        add_btn.clicked.connect(self._on_add)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget(0, len(self._HEADERS))
        self.table.setHorizontalHeaderLabels(self._HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.itemSelectionChanged.connect(self._reload_tutor_subjects)
        splitter.addWidget(self.table)

        subjects_box = QGroupBox("מקצועות ושכבות של החונכת הנבחרת")
        subjects_layout = QVBoxLayout(subjects_box)

        # Row 1: subject + units range.
        add_subject_row = QHBoxLayout()
        add_subject_row.addWidget(QLabel("מקצוע:"))
        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(160)
        add_subject_row.addWidget(self.subject_combo)

        add_subject_row.addWidget(QLabel('יח"ל מ-'))
        self.units_min_spin = QSpinBox()
        self.units_min_spin.setRange(UNITS_MIN, UNITS_MAX)
        self.units_min_spin.setValue(3)
        add_subject_row.addWidget(self.units_min_spin)

        add_subject_row.addWidget(QLabel("עד"))
        self.units_max_spin = QSpinBox()
        self.units_max_spin.setRange(UNITS_MIN, UNITS_MAX)
        self.units_max_spin.setValue(5)
        add_subject_row.addWidget(self.units_max_spin)
        add_subject_row.addStretch(1)
        subjects_layout.addLayout(add_subject_row)

        # Row 2: grade checkboxes + add button.
        grades_row = QHBoxLayout()
        grades_row.addWidget(QLabel("שכבות:"))
        for grade in GRADES:
            check = QCheckBox(grade)
            self._grade_checks[grade] = check
            grades_row.addWidget(check)
        grades_row.addStretch(1)
        add_subject_btn = QPushButton("הוספת מקצוע / שכבות")
        add_subject_btn.clicked.connect(self._on_add_subject)
        grades_row.addWidget(add_subject_btn)
        subjects_layout.addLayout(grades_row)

        self.subjects_list = QListWidget()
        subjects_layout.addWidget(self.subjects_list)

        remove_subject_btn = QPushButton("הסרת שורה נבחרת")
        remove_subject_btn.setProperty("class", "secondary")
        remove_subject_btn.clicked.connect(self._on_remove_subject)
        subjects_layout.addWidget(remove_subject_btn)

        splitter.addWidget(subjects_box)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        constraints_btn = QPushButton("אילוצי שעות")
        constraints_btn.clicked.connect(self._on_edit_constraints)
        buttons.addWidget(constraints_btn)

        global_btn = QPushButton("אילוץ כללי (כל החונכות)")
        global_btn.setProperty("class", "secondary")
        global_btn.clicked.connect(self._on_edit_global_constraints)
        buttons.addWidget(global_btn)

        rename_btn = QPushButton("שינוי שם")
        rename_btn.setProperty("class", "secondary")
        rename_btn.clicked.connect(self._on_rename)
        buttons.addWidget(rename_btn)

        delete_btn = QPushButton("מחיקה")
        delete_btn.setProperty("class", "secondary")
        delete_btn.clicked.connect(self._on_delete)
        buttons.addWidget(delete_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    # --------------------------------------------------------------- helpers
    def _selected_tutor(self) -> tuple[int, str] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        tutor_id = int(item.data(Qt.ItemDataRole.UserRole))
        return tutor_id, item.text()

    def _reload_subject_combo(self) -> None:
        current = self.subject_combo.currentData()
        self.subject_combo.clear()
        for subject_id, name in self.controller.list_subjects():
            self.subject_combo.addItem(name, subject_id)
        if current is not None:
            idx = self.subject_combo.findData(current)
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)

    def _reload_tutor_subjects(self) -> None:
        self.subjects_list.clear()
        selected = self._selected_tutor()
        if selected is None:
            return
        tutor_id, _name = selected
        for row in self.controller.list_tutor_subjects(tutor_id):
            rng = (
                f"{row['units_min']}"
                if row["units_min"] == row["units_max"]
                else f"{row['units_min']}-{row['units_max']}"
            )
            text = f"{row['subject_name']}  ·  {row['grade']}  ·  {rng} יח\"ל"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.subjects_list.addItem(item)

    def _checked_grades(self) -> list[str]:
        return [g for g, chk in self._grade_checks.items() if chk.isChecked()]

    # --------------------------------------------------------------- actions
    def _on_add(self) -> None:
        try:
            self.controller.add_tutor(self.name_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self.name_edit.clear()
        self.refresh()

    def _on_add_subject(self) -> None:
        selected = self._selected_tutor()
        if selected is None:
            QMessageBox.information(
                self, "בחירת חונכת", "יש לבחור חונכת מהרשימה תחילה."
            )
            return
        if self.subject_combo.count() == 0:
            QMessageBox.information(
                self,
                "אין מקצועות",
                "יש להוסיף מקצועות (בלשונית שריון מקצועות או דרך ייבוא) תחילה.",
            )
            return
        grades = self._checked_grades()
        if not grades:
            QMessageBox.information(self, "שכבות", "יש לבחור לפחות שכבה אחת.")
            return

        tutor_id, _name = selected
        subject_id = int(self.subject_combo.currentData())
        try:
            self.controller.add_tutor_subject(
                tutor_id,
                subject_id,
                grades,
                self.units_min_spin.value(),
                self.units_max_spin.value(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        for chk in self._grade_checks.values():
            chk.setChecked(False)
        self.refresh()
        self._select_tutor_by_id(tutor_id)

    def _on_remove_subject(self) -> None:
        item = self.subjects_list.currentItem()
        if item is None:
            return
        tutor_subject_id = int(item.data(Qt.ItemDataRole.UserRole))
        self.controller.remove_tutor_subject(tutor_subject_id)
        selected = self._selected_tutor()
        self.refresh()
        if selected:
            self._select_tutor_by_id(selected[0])

    def _on_edit_constraints(self) -> None:
        selected = self._selected_tutor()
        if selected is None:
            QMessageBox.information(
                self, "בחירת חונכת", "יש לבחור חונכת מהרשימה תחילה."
            )
            return
        tutor_id, name = selected
        current = self.controller.get_unavailability(tutor_id)
        dialog = AvailabilityGridDialog(
            title=f"אילוצי שעות — {name}",
            instruction=(
                "סמנו את השעות שבהן החונכת אינה יכולה ללמד (אילוץ קבוע). "
                "תאים מסומנים באדום לא יהיו זמינים לשיבוץ."
            ),
            selected=current,
            parent=self,
        )
        if dialog.exec() == AvailabilityGridDialog.DialogCode.Accepted:
            self.controller.set_unavailability(tutor_id, dialog.selected_cells())
            self._select_tutor_by_id(tutor_id)

    def _on_edit_global_constraints(self) -> None:
        current = self.controller.get_global_unavailability()
        dialog = AvailabilityGridDialog(
            title="אילוץ כללי - חסימת שעות לכל החונכות",
            instruction=(
                "סמנו שעות שבהן אף חונכת אינה משבצת (למשל ארוחת צהריים או הפסקה). "
                "תאים אלה ייחסמו לכל החונכות במערכת ובשיבוץ האוטומטי."
            ),
            selected=current,
            parent=self,
        )
        if dialog.exec() == AvailabilityGridDialog.DialogCode.Accepted:
            self.controller.set_global_unavailability(dialog.selected_cells())

    def _on_rename(self) -> None:
        selected = self._selected_tutor()
        if selected is None:
            return
        tutor_id, name = selected
        new_name, ok = QInputDialog.getText(
            self, "שינוי שם", "שם חדש:", text=name
        )
        if not ok:
            return
        try:
            self.controller.rename_tutor(tutor_id, new_name)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self.refresh()
        self._select_tutor_by_id(tutor_id)

    def _on_delete(self) -> None:
        selected = self._selected_tutor()
        if selected is None:
            return
        tutor_id, name = selected
        confirm = QMessageBox.question(
            self,
            "מחיקת חונכת",
            f"למחוק את '{name}' ואת כל השיבוצים שלה?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.controller.delete_tutor(tutor_id)
        self.refresh()

    def _select_tutor_by_id(self, tutor_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and int(item.data(Qt.ItemDataRole.UserRole)) == tutor_id:
                self.table.selectRow(row)
                break

    # --------------------------------------------------------------- reload
    def refresh(self) -> None:
        self._reload_subject_combo()
        tutors = self.controller.list_tutors()
        selected = self._selected_tutor()
        selected_id = selected[0] if selected else None

        self.table.setRowCount(len(tutors))
        for row, tutor in enumerate(tutors):
            name_item = QTableWidgetItem(tutor["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, tutor["id"])
            self.table.setItem(row, 0, name_item)

            subjects_item = QTableWidgetItem(tutor["subjects_text"] or "—")
            self.table.setItem(row, 1, subjects_item)

        if selected_id is not None:
            self._select_tutor_by_id(selected_id)
        self._reload_tutor_subjects()
