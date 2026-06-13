"""Quick dialog to rename a study group and set its preferred tutor."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.controllers.grouping_controller import GroupingController


class GroupRenameDialog(QDialog):
    """Edit a group's display name and preferred tutor without changing members."""

    def __init__(
        self,
        controller: GroupingController,
        group_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.group_id = group_id
        self._group = controller.get_group(group_id)
        if self._group is None:
            raise ValueError("הקבוצה לא נמצאה")

        self.setWindowTitle("שינוי שם קבוצה")
        self.resize(420, 180)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("שם הקבוצה:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('לדוגמה: קבוצת חיזוק א\'')
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("חונכת מועדפת (לא חובה):"))
        self.tutor_combo = QComboBox()
        self.tutor_combo.setToolTip(
            "השיבוץ האוטומטי ינסה לשבץ את החונכת הזו, "
            "אך יבחר חונכת אחרת אם לא ניתן."
        )
        layout.addWidget(self.tutor_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("שמירה")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("ביטול")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self) -> None:
        group = self._group
        assert group is not None
        self.name_edit.setText(group["name"])

        self.tutor_combo.clear()
        self.tutor_combo.addItem("(ללא העדפה)", None)
        for tutor_id, tutor_name in self.controller.list_qualified_tutors(
            group["subject_id"], group["grade"], group["units"]
        ):
            self.tutor_combo.addItem(tutor_name, tutor_id)

        preferred = group.get("preferred_tutor_id")
        if preferred is not None:
            idx = self.tutor_combo.findData(preferred)
            if idx >= 0:
                self.tutor_combo.setCurrentIndex(idx)

    def group_name(self) -> str:
        return self.name_edit.text()

    def preferred_tutor_id(self) -> int | None:
        value = self.tutor_combo.currentData()
        return int(value) if value is not None else None
