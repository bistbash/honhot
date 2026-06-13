"""Dialog for creating or editing a student record."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import GRADES, LEVEL_MAX, LEVEL_MIN, UNITS_MAX, UNITS_MIN
from app.controllers.import_controller import ImportController


class StudentEditorDialog(QDialog):
    """Collect student fields for manual create or edit."""

    def __init__(
        self,
        controller: ImportController,
        subject_id: int,
        student_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.subject_id = subject_id
        self.student_id = student_id
        self._in_group = False
        self.setWindowTitle("עריכת תלמיד" if student_id else "הוספת תלמיד")
        self.resize(420, 320)
        self._build_ui()
        if student_id is not None:
            self._load()
        else:
            self._refresh_tutor_combo()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("שם:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("שכבה:"))
        self.grade_combo = QComboBox()
        for grade in GRADES:
            self.grade_combo.addItem(grade, grade)
        layout.addWidget(self.grade_combo)

        layout.addWidget(QLabel("מספר כיתה:"))
        self.class_spin = QSpinBox()
        self.class_spin.setRange(1, 15)
        layout.addWidget(self.class_spin)

        layout.addWidget(QLabel('יח"ל:'))
        self.units_spin = QSpinBox()
        self.units_spin.setRange(UNITS_MIN, UNITS_MAX)
        self.units_spin.valueChanged.connect(self._refresh_tutor_combo)
        layout.addWidget(self.units_spin)

        layout.addWidget(QLabel("רמת לימוד:"))
        self.level_spin = QSpinBox()
        self.level_spin.setRange(LEVEL_MIN, LEVEL_MAX)
        layout.addWidget(self.level_spin)

        self.tutor_label = QLabel("חונכת מועדפת (לא חובה):")
        layout.addWidget(self.tutor_label)
        self.tutor_combo = QComboBox()
        layout.addWidget(self.tutor_combo)

        self.group_hint = QLabel("")
        self.group_hint.setWordWrap(True)
        self.group_hint.setStyleSheet("color: #6b7895;")
        layout.addWidget(self.group_hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("שמירה")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("ביטול")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.grade_combo.currentIndexChanged.connect(self._refresh_tutor_combo)

    def _load(self) -> None:
        student = self.controller.get_student(self.student_id)  # type: ignore[arg-type]
        if student is None:
            return
        self.name_edit.setText(student["name"])
        idx = self.grade_combo.findData(student["grade"])
        if idx >= 0:
            self.grade_combo.setCurrentIndex(idx)
        self.class_spin.setValue(student["class_number"])
        self.units_spin.setValue(student["units"])
        self.level_spin.setValue(student["study_level"])
        self._in_group = student["study_group_id"] is not None
        if self._in_group:
            self.group_hint.setText(
                f"התלמיד בקבוצה: {student['group']}. "
                "שינוי שכבה/יח\"ל/רמה יוציא אותו מהקבוצה. "
                "חונכת מועדפת מוגדרת ברמת הקבוצה."
            )
            self.tutor_label.setVisible(False)
            self.tutor_combo.setVisible(False)
        else:
            self._refresh_tutor_combo()
            preferred = student.get("preferred_tutor_id")
            if preferred is not None:
                tidx = self.tutor_combo.findData(preferred)
                if tidx >= 0:
                    self.tutor_combo.setCurrentIndex(tidx)

    def _refresh_tutor_combo(self) -> None:
        if self._in_group:
            return
        grade = str(self.grade_combo.currentData())
        units = self.units_spin.value()
        preferred = self.preferred_tutor_id()
        self.tutor_combo.clear()
        self.tutor_combo.addItem("(ללא העדפה)", None)
        for tutor_id, tutor_name in self.controller.list_qualified_tutors(
            self.subject_id, grade, units
        ):
            self.tutor_combo.addItem(tutor_name, tutor_id)
        if preferred is not None:
            idx = self.tutor_combo.findData(preferred)
            if idx >= 0:
                self.tutor_combo.setCurrentIndex(idx)

    def name(self) -> str:
        return self.name_edit.text()

    def grade(self) -> str:
        return str(self.grade_combo.currentData())

    def class_number(self) -> int:
        return self.class_spin.value()

    def units(self) -> int:
        return self.units_spin.value()

    def study_level(self) -> int:
        return self.level_spin.value()

    def preferred_tutor_id(self) -> int | None:
        if self._in_group:
            return None
        value = self.tutor_combo.currentData()
        return int(value) if value is not None else None
