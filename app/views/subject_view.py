"""View for managing subjects: create/delete, weekly hours and reserved windows."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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


class SubjectView(QWidget):
    """Create subjects, set weekly hours per student and reserved time windows."""

    def __init__(self) -> None:
        super().__init__()
        self.controller = SubjectController()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Create a new subject ------------------------------------------
        create_box = QGroupBox("הוספת מקצוע")
        create_layout = QHBoxLayout(create_box)
        create_layout.addWidget(QLabel("שם:"))
        self.new_name_edit = QLineEdit()
        self.new_name_edit.setPlaceholderText("שם המקצוע")
        self.new_name_edit.returnPressed.connect(self._on_add_subject)
        create_layout.addWidget(self.new_name_edit, 1)

        create_layout.addWidget(QLabel("שעות שבועיות לתלמיד:"))
        self.new_hours_spin = QSpinBox()
        self.new_hours_spin.setRange(1, 20)
        self.new_hours_spin.setValue(1)
        create_layout.addWidget(self.new_hours_spin)

        add_btn = QPushButton("הוספה")
        add_btn.clicked.connect(self._on_add_subject)
        create_layout.addWidget(add_btn)
        layout.addWidget(create_box)

        # --- Selected subject settings -------------------------------------
        top = QHBoxLayout()
        top.addWidget(QLabel("מקצוע:"))
        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(220)
        self.subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        top.addWidget(self.subject_combo)

        top.addWidget(QLabel("שעות שבועיות לתלמיד:"))
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 20)
        self.hours_spin.valueChanged.connect(self._on_hours_changed)
        top.addWidget(self.hours_spin)

        delete_btn = QPushButton("מחיקת מקצוע")
        delete_btn.setProperty("class", "secondary")
        delete_btn.clicked.connect(self._on_delete_subject)
        top.addWidget(delete_btn)
        top.addStretch(1)
        layout.addLayout(top)

        layout.addWidget(
            QLabel(
                "לחצו על תאים כדי לסמן את הזמנים שבהם מותר לשבץ את המקצוע. "
                "מקצוע ללא סימון כלל אינו מוגבל בזמן."
            )
        )

        # Grid: rows = hours, columns = days.
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
        layout.addWidget(self.grid, 1)

        buttons = QHBoxLayout()
        save_btn = QPushButton("שמירת שריון")
        save_btn.clicked.connect(self._on_save)
        buttons.addWidget(save_btn)
        clear_btn = QPushButton("ניקוי הכל")
        clear_btn.setProperty("class", "secondary")
        clear_btn.clicked.connect(self._on_clear)
        buttons.addWidget(clear_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    # --------------------------------------------------------------- helpers
    def _current_subject_id(self) -> int | None:
        data = self.subject_combo.currentData()
        return int(data) if data is not None else None

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

    # --------------------------------------------------------------- actions
    def _on_add_subject(self) -> None:
        try:
            new_id = self.controller.add_subject(
                self.new_name_edit.text(), self.new_hours_spin.value()
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self.new_name_edit.clear()
        self.new_hours_spin.setValue(1)
        self.refresh()
        self._select_subject_by_id(new_id)

    def _on_delete_subject(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        name = self.subject_combo.currentText()
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

    def _on_hours_changed(self, value: int) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        try:
            self.controller.set_weekly_hours(subject_id, value)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))

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

    def _on_subject_changed(self) -> None:
        self._load_hours()
        self._load_windows()

    def _load_hours(self) -> None:
        subject_id = self._current_subject_id()
        self.hours_spin.blockSignals(True)
        if subject_id is None:
            self.hours_spin.setValue(1)
            self.hours_spin.setEnabled(False)
        else:
            self.hours_spin.setEnabled(True)
            self.hours_spin.setValue(self.controller.get_weekly_hours(subject_id))
        self.hours_spin.blockSignals(False)

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

    def _select_subject_by_id(self, subject_id: int) -> None:
        index = self.subject_combo.findData(subject_id)
        if index >= 0:
            self.subject_combo.setCurrentIndex(index)

    # --------------------------------------------------------------- reload
    def refresh(self) -> None:
        current = self._current_subject_id()
        self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        for subject in self.controller.list_subjects_detailed():
            label = f"{subject['name']}  ({subject['weekly_hours']} ש\"ש)"
            self.subject_combo.addItem(label, subject["id"])
        self.subject_combo.blockSignals(False)
        if current is not None:
            self._select_subject_by_id(current)
        self._load_hours()
        self._load_windows()
