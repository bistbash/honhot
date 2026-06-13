"""View for managing subjects: create/delete, weekly hours and reserved windows."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import DAYS, HOURS
from app.controllers.subject_controller import SubjectController

_RESERVED_BRUSH = QColor(45, 108, 223, 90)
_COL_ID = 0
_COL_NAME = 1
_COL_HOURS = 2


class SubjectView(QWidget):
    """Create subjects, set optional weekly hours and reserved time windows."""

    def __init__(self) -> None:
        super().__init__()
        self.controller = SubjectController()
        self._loading = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("מקצועות"))
        header.addStretch(1)
        add_btn = QPushButton("הוסף מקצוע")
        add_btn.clicked.connect(self._on_add_subject)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.subjects_table = QTableWidget(0, 3)
        self.subjects_table.setHorizontalHeaderLabels(
            ["", "שם המקצוע", "שעות שבועיות"]
        )
        self.subjects_table.setColumnHidden(_COL_ID, True)
        self.subjects_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.subjects_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.subjects_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.subjects_table.horizontalHeader().setSectionResizeMode(
            _COL_NAME, QHeaderView.ResizeMode.Stretch
        )
        self.subjects_table.horizontalHeader().setSectionResizeMode(
            _COL_HOURS, QHeaderView.ResizeMode.ResizeToContents
        )
        self.subjects_table.verticalHeader().setVisible(False)
        self.subjects_table.itemChanged.connect(self._on_item_changed)
        self.subjects_table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.subjects_table)

        table_actions = QHBoxLayout()
        delete_btn = QPushButton("מחיקת מקצוע")
        delete_btn.setProperty("class", "secondary")
        delete_btn.clicked.connect(self._on_delete_subject)
        table_actions.addWidget(delete_btn)
        table_actions.addStretch(1)
        layout.addLayout(table_actions)

        self.details_box = QGroupBox("הגדרות מקצוע נבחר")
        details_layout = QVBoxLayout(self.details_box)

        hours_row = QHBoxLayout()
        hours_row.addWidget(QLabel("שעות שבועיות לתלמיד:"))
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 20)
        self.hours_spin.setValue(1)
        self.hours_spin.valueChanged.connect(self._on_hours_changed)
        hours_row.addWidget(self.hours_spin)
        self.hours_undefined_cb = QCheckBox("לא מוגדר (שיבוץ ידני בלבד)")
        self.hours_undefined_cb.toggled.connect(self._on_hours_undefined_toggled)
        hours_row.addWidget(self.hours_undefined_cb)
        hours_row.addStretch(1)
        details_layout.addLayout(hours_row)

        details_layout.addWidget(
            QLabel(
                "לחצו על תאים כדי לסמן את הזמנים שבהם מותר לשבץ את המקצוע. "
                "מקצוע ללא סימון כלל אינו מוגבל בזמן."
            )
        )

        self.grid = QTableWidget(len(HOURS), len(DAYS))
        self.grid.setHorizontalHeaderLabels(DAYS)
        self.grid.setVerticalHeaderLabels([f"שעה {h}" for h in HOURS])
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.grid.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.grid.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for r in range(len(HOURS)):
            for c in range(len(DAYS)):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid.setItem(r, c, item)
        self.grid.cellClicked.connect(self._on_cell_clicked)
        details_layout.addWidget(self.grid, 1)

        buttons = QHBoxLayout()
        save_btn = QPushButton("שמירת שריון")
        save_btn.clicked.connect(self._on_save)
        buttons.addWidget(save_btn)
        clear_btn = QPushButton("ניקוי הכל")
        clear_btn.setProperty("class", "secondary")
        clear_btn.clicked.connect(self._on_clear)
        buttons.addWidget(clear_btn)
        buttons.addStretch(1)
        details_layout.addLayout(buttons)

        self.details_box.setEnabled(False)
        layout.addWidget(self.details_box, 1)

    # --------------------------------------------------------------- helpers
    def _current_subject_id(self) -> int | None:
        row = self.subjects_table.currentRow()
        if row < 0:
            return None
        item = self.subjects_table.item(row, _COL_ID)
        if item is None:
            return None
        return int(item.text())

    def _set_cell_reserved(self, row: int, col: int, reserved: bool) -> None:
        item = self.grid.item(row, col)
        if item is None:
            return
        if reserved:
            item.setText("✓")
            item.setBackground(QBrush(_RESERVED_BRUSH))
            item.setData(Qt.ItemDataRole.UserRole, True)
        else:
            item.setText("")
            item.setData(Qt.ItemDataRole.UserRole, False)
            item.setBackground(QBrush(Qt.GlobalColor.transparent))

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.grid.item(row, col)
        if item is None:
            return
        reserved = bool(item.data(Qt.ItemDataRole.UserRole))
        self._set_cell_reserved(row, col, not reserved)

    def _collect_cells(self) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for r, hour in enumerate(HOURS):
            for c in range(len(DAYS)):
                item = self.grid.item(r, c)
                if item is not None and bool(item.data(Qt.ItemDataRole.UserRole)):
                    cells.add((c, hour))
        return cells

    def _format_hours_cell(self, weekly_hours: int | None) -> str:
        if weekly_hours is None:
            return "לא מוגדר"
        return str(weekly_hours)

    def _select_subject_by_id(self, subject_id: int) -> None:
        for row in range(self.subjects_table.rowCount()):
            item = self.subjects_table.item(row, _COL_ID)
            if item is not None and int(item.text()) == subject_id:
                self.subjects_table.selectRow(row)
                return

    # --------------------------------------------------------------- actions
    def _on_add_subject(self) -> None:
        name, ok = QInputDialog.getText(self, "הוספת מקצוע", "שם המקצוע:")
        if not ok or not name.strip():
            return
        try:
            new_id = self.controller.add_subject(name)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self.refresh()
        self._select_subject_by_id(new_id)

    def _on_delete_subject(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        row = self.subjects_table.currentRow()
        name_item = self.subjects_table.item(row, _COL_NAME)
        name = name_item.text() if name_item else ""
        confirm = QMessageBox.question(
            self,
            "מחיקת מקצוע",
            f"למחוק את המקצוע '{name}' וכל הנתונים הקשורים אליו "
            "(תלמידים, קבוצות ושיבוצים)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.controller.delete_subject(subject_id)
        self.refresh()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != _COL_NAME:
            return
        row = item.row()
        id_item = self.subjects_table.item(row, _COL_ID)
        if id_item is None:
            return
        subject_id = int(id_item.text())
        try:
            self.controller.rename_subject(subject_id, item.text())
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            self.refresh()

    def _on_hours_undefined_toggled(self, checked: bool) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None or self._loading:
            return
        self.hours_spin.setEnabled(not checked)
        try:
            value = None if checked else self.hours_spin.value()
            self.controller.set_weekly_hours(subject_id, value)
            self._update_hours_cell(subject_id, value)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))

    def _on_hours_changed(self, value: int) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None or self._loading or self.hours_undefined_cb.isChecked():
            return
        try:
            self.controller.set_weekly_hours(subject_id, value)
            self._update_hours_cell(subject_id, value)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))

    def _update_hours_cell(self, subject_id: int, weekly_hours: int | None) -> None:
        for row in range(self.subjects_table.rowCount()):
            id_item = self.subjects_table.item(row, _COL_ID)
            if id_item is not None and int(id_item.text()) == subject_id:
                hours_item = self.subjects_table.item(row, _COL_HOURS)
                if hours_item is not None:
                    self._loading = True
                    hours_item.setText(self._format_hours_cell(weekly_hours))
                    self._loading = False
                break

    def _on_save(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            QMessageBox.information(self, "אין מקצוע", "אין מקצוע נבחר לשמירה.")
            return
        self.controller.set_windows(subject_id, self._collect_cells())
        QMessageBox.information(self, "נשמר", "השריון נשמר בהצלחה.")

    def _on_clear(self) -> None:
        for r in range(len(HOURS)):
            for c in range(len(DAYS)):
                self._set_cell_reserved(r, c, False)

    def _on_selection_changed(self) -> None:
        subject_id = self._current_subject_id()
        self.details_box.setEnabled(subject_id is not None)
        self._load_hours()
        self._load_windows()

    def _load_hours(self) -> None:
        subject_id = self._current_subject_id()
        self._loading = True
        self.hours_spin.blockSignals(True)
        self.hours_undefined_cb.blockSignals(True)
        if subject_id is None:
            self.hours_spin.setEnabled(False)
            self.hours_undefined_cb.setEnabled(False)
        else:
            weekly = self.controller.get_weekly_hours(subject_id)
            undefined = weekly is None
            self.hours_undefined_cb.setEnabled(True)
            self.hours_undefined_cb.setChecked(undefined)
            self.hours_spin.setEnabled(not undefined)
            if undefined:
                self.hours_spin.setValue(1)
            else:
                self.hours_spin.setValue(weekly)
        self.hours_spin.blockSignals(False)
        self.hours_undefined_cb.blockSignals(False)
        self._loading = False

    def _load_windows(self) -> None:
        self._on_clear()
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        windows = self.controller.get_windows(subject_id)
        hour_to_row = {hour: r for r, hour in enumerate(HOURS)}
        for day, hour in windows:
            if day < len(DAYS) and hour in hour_to_row:
                self._set_cell_reserved(hour_to_row[hour], day, True)

    # --------------------------------------------------------------- reload
    def refresh(self) -> None:
        current = self._current_subject_id()
        self._loading = True
        self.subjects_table.blockSignals(True)
        self.subjects_table.setRowCount(0)
        for subject in self.controller.list_subjects_detailed():
            row = self.subjects_table.rowCount()
            self.subjects_table.insertRow(row)
            id_item = QTableWidgetItem(str(subject["id"]))
            name_item = QTableWidgetItem(subject["name"])
            hours_item = QTableWidgetItem(
                self._format_hours_cell(subject["weekly_hours"])
            )
            hours_item.setFlags(hours_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.subjects_table.setItem(row, _COL_ID, id_item)
            self.subjects_table.setItem(row, _COL_NAME, name_item)
            self.subjects_table.setItem(row, _COL_HOURS, hours_item)
        self.subjects_table.blockSignals(False)
        self._loading = False
        if current is not None:
            self._select_subject_by_id(current)
        elif self.subjects_table.rowCount() > 0:
            self.subjects_table.selectRow(0)
        else:
            self.details_box.setEnabled(False)
            self._on_clear()
