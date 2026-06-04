"""The timetable tab: tutor selector, weekly grid and entity sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.controllers.schedule_controller import ScheduleController
from app.views.timetable.entity_sidebar import EntitySidebar
from app.views.timetable.timetable_grid import TimetableGrid


class TimetableView(QWidget):
    """Drag students/groups from the sidebar onto a tutor's weekly grid."""

    def __init__(self) -> None:
        super().__init__()
        self.controller = ScheduleController()
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(QLabel("חונכת:"))
        self.tutor_combo = QComboBox()
        self.tutor_combo.setMinimumWidth(220)
        self.tutor_combo.currentIndexChanged.connect(self._reload_grid)
        top.addWidget(self.tutor_combo)
        self.load_label = QLabel("")
        self.load_label.setStyleSheet("color: #6b7895; font-weight: 600;")
        top.addWidget(self.load_label)
        top.addStretch(1)
        auto_btn = QPushButton("שיבוץ אוטומטי")
        auto_btn.clicked.connect(self._on_auto_assign)
        top.addWidget(auto_btn)
        refresh_btn = QPushButton("רענון")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.grid = TimetableGrid()
        self.grid.entityDropped.connect(self._on_entity_dropped)
        self.grid.unassignRequested.connect(self._on_unassign)
        self.grid.moveRequested.connect(self._on_move)
        splitter.addWidget(self.grid)

        sidebar_box = QGroupBox("תלמידים וקבוצות לשיבוץ")
        sidebar_layout = QVBoxLayout(sidebar_box)
        sidebar_layout.addWidget(
            QLabel("גררו פריט אל המשבצת הרצויה. ירוק = מותר לשבץ.")
        )
        self.sidebar = EntitySidebar()
        self.sidebar.entitySelected.connect(self._on_entity_selected)
        self.sidebar.selectionCleared.connect(lambda: self.grid.highlight_allowed(None))
        sidebar_layout.addWidget(self.sidebar)
        splitter.addWidget(sidebar_box)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.hint_label = QLabel(
            "טיפ: גררו שיעור לתא פנוי כדי להעביר אותו · לחיצה ימנית או מקש "
            "Delete מוחקים שיעור."
        )
        layout.addWidget(self.hint_label)

    # --------------------------------------------------------------- helpers
    def _current_tutor_id(self) -> int | None:
        data = self.tutor_combo.currentData()
        return int(data) if data is not None else None

    # --------------------------------------------------------------- actions
    def _on_entity_selected(self, entity_type: str, entity_id: int) -> None:
        allowed = self.controller.reserved_cells_for_entity(entity_type, entity_id)
        self.grid.highlight_allowed(allowed)
        if allowed is None:
            self.hint_label.setText("המקצוע אינו מוגבל בזמן - ניתן לשבץ בכל משבצת.")
        else:
            self.hint_label.setText(
                "המקצוע משוריין - ניתן לשבץ רק במשבצות הירוקות."
            )

    def _on_entity_dropped(
        self, day: int, hour: int, entity_type: str, entity_id: int
    ) -> None:
        tutor_id = self._current_tutor_id()
        if tutor_id is None:
            QMessageBox.warning(self, "אין חונכת", "יש לבחור חונכת פעילה תחילה.")
            return
        result = self.controller.try_assign(
            tutor_id, day, hour, entity_type, entity_id
        )
        if not result.ok:
            QMessageBox.warning(self, "השיבוץ נדחה", result.message)
            return
        self._reload_grid()
        self._reload_sidebar()

    def _on_unassign(self, day: int, hour: int) -> None:
        tutor_id = self._current_tutor_id()
        if tutor_id is None:
            return
        self.controller.unassign(tutor_id, day, hour)
        self._reload_grid()
        self._reload_sidebar()

    def _on_move(
        self, src_day: int, src_hour: int, dst_day: int, dst_hour: int
    ) -> None:
        tutor_id = self._current_tutor_id()
        if tutor_id is None:
            return
        result = self.controller.move_assignment(
            tutor_id, src_day, src_hour, dst_day, dst_hour
        )
        if not result.ok:
            QMessageBox.warning(self, "ההעברה נדחתה", result.message)
        self._reload_grid()
        self._reload_sidebar()

    def _on_auto_assign(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("שיבוץ אוטומטי")
        box.setText(
            "כיצד לבצע את השיבוץ האוטומטי?\n\n"
            "המערכת תאזן את מספר השעות בין החונכות תוך כיבוד "
            "המקצועות, היח\"ל והאילוצים."
        )
        reset_btn = box.addButton(
            "איפוס ושיבוץ הכל מחדש", QMessageBox.ButtonRole.DestructiveRole
        )
        fill_btn = box.addButton(
            "השלמת שיבוץ לישויות שטרם שובצו", QMessageBox.ButtonRole.AcceptRole
        )
        box.addButton("ביטול", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is reset_btn:
            clear_existing = True
        elif clicked is fill_btn:
            clear_existing = False
        else:
            return

        summary = self.controller.auto_assign(clear_existing)
        self.refresh()
        self._show_auto_summary(summary)

    def _show_auto_summary(self, summary) -> None:
        text = f"שובצו {summary.assigned} שעות."

        active_loads = [hours for _name, hours in summary.tutor_loads if hours]
        if summary.tutor_loads:
            loads = "\n".join(
                f"  {name}: {hours} שעות" for name, hours in summary.tutor_loads
            )
            text += "\n\nעומס לפי חונכת:\n" + loads
            if active_loads:
                spread = max(active_loads) - min(active_loads)
                text += (
                    f"\n\nאיזון: פער של {spread} שעות בין החונכת העמוסה ביותר "
                    f"({max(active_loads)}) לפנויה ביותר ({min(active_loads)})."
                )

        box = QMessageBox(self)
        box.setWindowTitle("שיבוץ אוטומטי הושלם")
        box.setText(text)
        if summary.unassigned_labels:
            box.setIcon(QMessageBox.Icon.Warning)
            preview = "\n".join(summary.unassigned_labels[:40])
            if len(summary.unassigned_labels) > 40:
                preview += f"\n... ועוד {len(summary.unassigned_labels) - 40}"
            box.setDetailedText(
                f"{len(summary.unassigned_labels)} ישויות לא שובצו במלואן "
                f"(אין חונכת מתאימה/פנויה):\n\n{preview}"
            )
        else:
            box.setIcon(QMessageBox.Icon.Information)
        box.exec()

    # --------------------------------------------------------------- reload
    def _reload_grid(self) -> None:
        tutor_id = self._current_tutor_id()
        if tutor_id is None:
            self.grid.populate({})
            self.load_label.setText("")
            return
        slots = self.controller.slots_for_tutor(tutor_id)
        self.grid.populate(
            slots,
            self.controller.unavailable_cells_for_tutor(tutor_id),
            self.controller.global_unavailable_cells(),
        )
        self.load_label.setText(f"·  {len(slots)} שעות שבועיות משובצות")

    def _reload_sidebar(self) -> None:
        self.sidebar.set_entities(self.controller.schedulable_entities())

    def refresh(self) -> None:
        """Reload tutors, grid and sidebar from the database."""
        current = self.tutor_combo.currentText()
        self.tutor_combo.blockSignals(True)
        self.tutor_combo.clear()
        for tutor_id, name in self.controller.list_tutors():
            self.tutor_combo.addItem(name, tutor_id)
        self.tutor_combo.blockSignals(False)
        if current:
            idx = self.tutor_combo.findText(current)
            if idx >= 0:
                self.tutor_combo.setCurrentIndex(idx)
        self._reload_grid()
        self._reload_sidebar()
