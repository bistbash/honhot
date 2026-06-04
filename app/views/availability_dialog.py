"""Reusable dialog with a day x hour grid for selecting (day, hour) cells.

Used to edit a tutor's recurring unavailability (the cells they cannot teach).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import DAYS, HOURS

_BLOCKED_BRUSH = QColor(214, 69, 69, 110)


class AvailabilityGridDialog(QDialog):
    """Modal dialog: toggle (day, hour) cells on a weekly grid."""

    def __init__(
        self,
        title: str,
        instruction: str,
        selected: set[tuple[int, int]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 520)
        self._selected = set(selected or set())
        self._build_ui(instruction)
        self._load_selection()

    def _build_ui(self, instruction: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel(instruction))

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

        clear_btn = QPushButton("ניקוי הכל")
        clear_btn.setProperty("class", "secondary")
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_cell(self, row: int, col: int, blocked: bool) -> None:
        item = self.grid.item(row, col)
        if item is None:
            return
        if blocked:
            item.setText("✗")
            item.setBackground(QBrush(_BLOCKED_BRUSH))
            item.setData(Qt.ItemDataRole.UserRole, True)
        else:
            item.setText("")
            item.setData(Qt.ItemDataRole.UserRole, False)
            item.setBackground(QBrush(Qt.GlobalColor.transparent))

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.grid.item(row, col)
        if item is None:
            return
        self._set_cell(row, col, not bool(item.data(Qt.ItemDataRole.UserRole)))

    def _on_clear(self) -> None:
        for r in range(len(HOURS)):
            for c in range(len(DAYS)):
                self._set_cell(r, c, False)

    def _load_selection(self) -> None:
        hour_to_row = {hour: r for r, hour in enumerate(HOURS)}
        for day, hour in self._selected:
            if day < len(DAYS) and hour in hour_to_row:
                self._set_cell(hour_to_row[hour], day, True)

    def selected_cells(self) -> set[tuple[int, int]]:
        """Return the currently selected (day, hour) cells."""
        cells: set[tuple[int, int]] = set()
        for r, hour in enumerate(HOURS):
            for c in range(len(DAYS)):
                item = self.grid.item(r, c)
                if item is not None and bool(item.data(Qt.ItemDataRole.UserRole)):
                    cells.add((c, hour))
        return cells
