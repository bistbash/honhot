"""QAbstractTableModel presenting study-group suggestions with selection."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from app.services.grouping_engine import GroupSuggestion


class SuggestionsTableModel(QAbstractTableModel):
    """Read-only table of group suggestions with a checkable first column."""

    HEADERS = ["בחירה", "שכבה", 'יח"ל', "רמה", "מספר תלמידים", "תלמידים"]
    COL_CHECK = 0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suggestions: list[GroupSuggestion] = []
        self._checked: list[bool] = []

    # ------------------------------------------------------------------ data
    def set_suggestions(self, suggestions: list[GroupSuggestion]) -> None:
        self.beginResetModel()
        self._suggestions = list(suggestions)
        self._checked = [True] * len(self._suggestions)
        self.endResetModel()

    def suggestion_at(self, row: int) -> GroupSuggestion:
        return self._suggestions[row]

    def checked_suggestions(self) -> list[GroupSuggestion]:
        return [
            s for s, checked in zip(self._suggestions, self._checked) if checked
        ]

    # -------------------------------------------------------- Qt model API
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._suggestions)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.COL_CHECK:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        suggestion = self._suggestions[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.CheckStateRole and col == self.COL_CHECK:
            return (
                Qt.CheckState.Checked
                if self._checked[index.row()]
                else Qt.CheckState.Unchecked
            )

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_CHECK:
                return ""
            if col == 1:
                return suggestion.key.grade
            if col == 2:
                return str(suggestion.key.units)
            if col == 3:
                return str(suggestion.key.study_level)
            if col == 4:
                return str(suggestion.size)
            if col == 5:
                return ", ".join(m.name for m in suggestion.members)
        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if (
            index.isValid()
            and index.column() == self.COL_CHECK
            and role == Qt.ItemDataRole.CheckStateRole
        ):
            self._checked[index.row()] = Qt.CheckState(value) == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [role])
            return True
        return False
