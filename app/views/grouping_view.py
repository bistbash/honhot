"""View for reviewing group suggestions and creating study groups."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.controllers.grouping_controller import GroupingController
from app.views.group_editor_dialog import GroupEditorDialog
from app.views.group_rename_dialog import GroupRenameDialog
from app.views.qt_models.groups_table_model import SuggestionsTableModel


class GroupingView(QWidget):
    """Suggest and create study groups within a selected subject."""

    def __init__(self) -> None:
        super().__init__()
        self.controller = GroupingController()
        self.model = SuggestionsTableModel(self)
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(QLabel("מקצוע:"))
        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(220)
        self.subject_combo.currentIndexChanged.connect(self._reload)
        top.addWidget(self.subject_combo)

        top.addWidget(QLabel("גודל קבוצה מקסימלי:"))
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(0, 30)
        self.max_size_spin.setValue(0)
        self.max_size_spin.setSpecialValueText("ללא הגבלה")
        self.max_size_spin.setToolTip(
            "0 = קבוצות גדולות ככל הניתן. ערך גדול מ-0 יחלק קבוצה גדולה "
            "למספר קבוצות מאוזנות בגודלן."
        )
        self.max_size_spin.valueChanged.connect(self._reload)
        top.addWidget(self.max_size_spin)

        top.addStretch(1)
        refresh_btn = QPushButton("רענון הצעות")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self._reload)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        # Suggestions box.
        suggestions_box = QGroupBox("הצעות לקבוצות לימוד (שכבה + יח\"ל + רמה זהים)")
        sug_layout = QVBoxLayout(suggestions_box)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        sug_layout.addWidget(self.table)

        sug_buttons = QHBoxLayout()
        create_btn = QPushButton("יצירת קבוצות מהמסומנות")
        create_btn.clicked.connect(self._on_create_groups)
        sug_buttons.addWidget(create_btn)
        auto_btn = QPushButton("קיבוץ אוטומטי (כל ההצעות)")
        auto_btn.setProperty("class", "secondary")
        auto_btn.clicked.connect(self._on_auto_group)
        sug_buttons.addWidget(auto_btn)
        sug_buttons.addStretch(1)
        sug_layout.addLayout(sug_buttons)
        layout.addWidget(suggestions_box, 1)

        # Existing groups box.
        groups_box = QGroupBox("קבוצות קיימות")
        grp_layout = QVBoxLayout(groups_box)
        self.groups_list = QListWidget()
        self.groups_list.itemDoubleClicked.connect(lambda _i: self._on_edit_group())
        grp_layout.addWidget(self.groups_list)

        grp_buttons = QHBoxLayout()
        manual_btn = QPushButton("יצירת קבוצה ידנית")
        manual_btn.clicked.connect(self._on_create_manual)
        grp_buttons.addWidget(manual_btn)

        edit_btn = QPushButton("עריכת הקבוצה הנבחרת")
        edit_btn.setProperty("class", "secondary")
        edit_btn.clicked.connect(self._on_edit_group)
        grp_buttons.addWidget(edit_btn)

        rename_btn = QPushButton("שינוי שם")
        rename_btn.setProperty("class", "secondary")
        rename_btn.clicked.connect(self._on_rename_group)
        grp_buttons.addWidget(rename_btn)

        disband_btn = QPushButton("פירוק הקבוצה הנבחרת")
        disband_btn.setProperty("class", "secondary")
        disband_btn.clicked.connect(self._on_disband)
        grp_buttons.addWidget(disband_btn)
        grp_buttons.addStretch(1)
        grp_layout.addLayout(grp_buttons)
        layout.addWidget(groups_box, 1)

    # --------------------------------------------------------------- actions
    def _current_subject_id(self) -> int | None:
        data = self.subject_combo.currentData()
        return int(data) if data is not None else None

    def _on_create_groups(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        chosen = self.model.checked_suggestions()
        if not chosen:
            QMessageBox.information(self, "אין בחירה", "לא נבחרו קבוצות ליצירה.")
            return
        created = 0
        for suggestion in chosen:
            self.controller.create_group(subject_id, suggestion)
            created += 1
        QMessageBox.information(self, "הקבוצות נוצרו", f"נוצרו {created} קבוצות לימוד.")
        self._reload()

    def _on_auto_group(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        suggestions = self.controller.suggestions_for_subject(
            subject_id, self.max_size_spin.value()
        )
        if not suggestions:
            QMessageBox.information(
                self,
                "אין הצעות",
                "אין תלמידים בודדים שניתן לקבץ במקצוע זה.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "קיבוץ אוטומטי",
            f"ליצור אוטומטית {len(suggestions)} קבוצות לימוד מכלל "
            "התלמידים הבודדים המתאימים?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for suggestion in suggestions:
            self.controller.create_group(subject_id, suggestion)
        QMessageBox.information(
            self, "הקבוצות נוצרו", f"נוצרו {len(suggestions)} קבוצות לימוד."
        )
        self._reload()

    def _on_create_manual(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            QMessageBox.information(self, "אין מקצוע", "יש לבחור מקצוע תחילה.")
            return
        dialog = GroupEditorDialog(self.controller, subject_id, parent=self)
        if dialog.exec() != GroupEditorDialog.DialogCode.Accepted:
            return
        try:
            self.controller.create_manual_group(
                subject_id,
                dialog.group_name(),
                dialog.selected_member_ids(),
                preferred_tutor_id=dialog.preferred_tutor_id(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self._reload()

    def _on_edit_group(self) -> None:
        item = self.groups_list.currentItem()
        if item is None:
            QMessageBox.information(self, "אין בחירה", "יש לבחור קבוצה לעריכה.")
            return
        group_id = int(item.data(256))  # Qt.UserRole
        subject_id = self._current_subject_id()
        if subject_id is None:
            return
        dialog = GroupEditorDialog(
            self.controller, subject_id, group_id=group_id, parent=self
        )
        if dialog.exec() != GroupEditorDialog.DialogCode.Accepted:
            return
        ids = dialog.selected_member_ids()
        if not ids:
            confirm = QMessageBox.question(
                self,
                "פירוק קבוצה",
                "לא נבחרו תלמידים. לפרק את הקבוצה?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.controller.disband_group(group_id)
                self._reload()
            return
        try:
            self.controller.set_group_members(
                group_id,
                dialog.group_name(),
                ids,
                preferred_tutor_id=dialog.preferred_tutor_id(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self._reload()

    def _on_rename_group(self) -> None:
        item = self.groups_list.currentItem()
        if item is None:
            QMessageBox.information(self, "אין בחירה", "יש לבחור קבוצה לשינוי שם.")
            return
        group_id = int(item.data(256))  # Qt.UserRole
        try:
            dialog = GroupRenameDialog(self.controller, group_id, parent=self)
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        if dialog.exec() != GroupRenameDialog.DialogCode.Accepted:
            return
        try:
            self.controller.set_group_details(
                group_id,
                dialog.group_name(),
                preferred_tutor_id=dialog.preferred_tutor_id(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "שגיאה", str(exc))
            return
        self._reload()

    def _on_disband(self) -> None:
        item = self.groups_list.currentItem()
        if item is None:
            return
        group_id = int(item.data(256))  # Qt.UserRole
        confirm = QMessageBox.question(
            self,
            "פירוק קבוצה",
            "לפרק את הקבוצה? התלמידים יחזרו לרשימת הבודדים.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.controller.disband_group(group_id)
        self._reload()

    # --------------------------------------------------------------- reload
    def _reload(self) -> None:
        subject_id = self._current_subject_id()
        if subject_id is None:
            self.model.set_suggestions([])
            self.groups_list.clear()
            return

        self.model.set_suggestions(
            self.controller.suggestions_for_subject(
                subject_id, self.max_size_spin.value()
            )
        )

        self.groups_list.clear()
        for group in self.controller.list_groups(subject_id):
            members = ", ".join(group["members"])
            tutor_line = ""
            if group.get("preferred_tutor_name"):
                tutor_line = f"\n    חונכת מועדפת: {group['preferred_tutor_name']}"
            text = (
                f"{group['name']}  -  {len(group['members'])} תלמידים"
                f"\n    {members}{tutor_line}"
            )
            item = QListWidgetItem(text)
            item.setData(256, group["id"])  # Qt.UserRole
            self.groups_list.addItem(item)

    def refresh(self) -> None:
        """Reload subjects and suggestions from the database."""
        current = self.subject_combo.currentText()
        self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        for subject_id, name in self.controller.list_subjects():
            self.subject_combo.addItem(name, subject_id)
        self.subject_combo.blockSignals(False)
        if current:
            idx = self.subject_combo.findText(current)
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)
        self._reload()
