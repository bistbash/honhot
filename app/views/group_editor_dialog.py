"""Dialog for creating or editing a study group by hand-picking members."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
from app.database import session_scope
from app.models import Student
from sqlalchemy import select


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
        self._group_grade: str | None = None
        self._group_units: int | None = None
        self._saved_preferred_tutor_id: int | None = None
        self.setWindowTitle(
            "עריכת קבוצת לימוד" if group_id else "יצירת קבוצת לימוד ידנית"
        )
        self.resize(520, 600)
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
                self._group_grade = group["grade"]
                self._group_units = group["units"]
                self._saved_preferred_tutor_id = group.get("preferred_tutor_id")
            for member in self.controller.group_members(self.group_id):
                self._add_item(member, checked=True)
                seen.add(member["id"])
        for student in self.controller.list_ungrouped_students(self.subject_id):
            if student["id"] not in seen:
                self._add_item(student, checked=False)
        self._update_count()

    def _update_count(self) -> None:
        self.count_label.setText(f"נבחרו {len(self.selected_member_ids())} תלמידים")
        self._refresh_tutor_combo()

    def _refresh_tutor_combo(self) -> None:
        grade, units = self._resolve_grade_units()
        preferred = self.preferred_tutor_id()
        if preferred is None:
            preferred = self._saved_preferred_tutor_id

        self.tutor_combo.blockSignals(True)
        self.tutor_combo.clear()
        self.tutor_combo.addItem("(ללא העדפה)", None)

        if grade is not None and units is not None:
            for tutor_id, tutor_name in self.controller.list_qualified_tutors(
                self.subject_id, grade, units
            ):
                self.tutor_combo.addItem(tutor_name, tutor_id)

        if preferred is not None:
            idx = self.tutor_combo.findData(preferred)
            if idx >= 0:
                self.tutor_combo.setCurrentIndex(idx)
        self.tutor_combo.blockSignals(False)

    def _resolve_grade_units(self) -> tuple[str | None, int | None]:
        member_ids = self.selected_member_ids()
        if not member_ids:
            if self._group_grade is not None and self._group_units is not None:
                return self._group_grade, self._group_units
            return None, None

        with session_scope() as session:
            students = session.scalars(
                select(Student).where(Student.id.in_(member_ids))
            ).all()
        grades = {s.grade for s in students}
        units_set = {s.units for s in students}
        if len(grades) == 1 and len(units_set) == 1:
            return grades.pop(), units_set.pop()
        return None, None

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

    def preferred_tutor_id(self) -> int | None:
        value = self.tutor_combo.currentData()
        return int(value) if value is not None else None
