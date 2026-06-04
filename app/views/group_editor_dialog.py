"""Dialog for creating or editing a study group by hand-picking members."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.grouping_controller import GroupingController


class GroupEditorDialog(QDialog):
    """Pick members (and a name) for a new or existing study group.

    Members are chosen from the subject's ungrouped students (plus the group's
    current members when editing) via a checkable list. The dialog only collects
    input; persistence is performed by the caller through the controller.
    """

    def __init__(
        self,
        controller: GroupingController,
        subject_id: int,
        group_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.subject_id = subject_id
        self.group_id = group_id
        self.setWindowTitle(
            "עריכת קבוצת לימוד" if group_id else "יצירת קבוצת לימוד ידנית"
        )
        self.resize(520, 560)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("שם הקבוצה (לא חובה):"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("יושלם אוטומטית אם יישאר ריק")
        layout.addWidget(self.name_edit)

        layout.addWidget(
            QLabel(
                "סמנו את התלמידים שיכללו בקבוצה. כל החברים חייבים אותה שכבה "
                'ואותם יח"ל (רמת לימוד יכולה להיות שונה).'
            )
        )
        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        self.count_label = QLabel("")
        layout.addWidget(self.count_label)
        self.list.itemChanged.connect(self._update_count)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("שמירה")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("ביטול")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_item(self, student: dict, checked: bool) -> None:
        item = QListWidgetItem(student["label"])
        item.setData(Qt.ItemDataRole.UserRole, student["id"])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        self.list.addItem(item)

    def _load(self) -> None:
        seen: set[int] = set()
        if self.group_id is not None:
            group = self.controller.get_group(self.group_id)
            if group:
                self.name_edit.setText(group["name"])
            for member in self.controller.group_members(self.group_id):
                self._add_item(member, checked=True)
                seen.add(member["id"])
        for student in self.controller.list_ungrouped_students(self.subject_id):
            if student["id"] not in seen:
                self._add_item(student, checked=False)
        self._update_count()

    def _update_count(self) -> None:
        self.count_label.setText(f"נבחרו {len(self.selected_member_ids())} תלמידים")

    # --------------------------------------------------------------- results
    def selected_member_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def group_name(self) -> str:
        return self.name_edit.text()
