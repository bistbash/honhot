"""Overview dashboard: KPIs, coverage, tutor balance and action items."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.controllers.dashboard_controller import DashboardController, Overview


class _KpiCard(QFrame):
    """A small card showing a big number with a caption."""

    def __init__(self, caption: str) -> None:
        super().__init__()
        self.setObjectName("kpiCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)
        self.value_label = QLabel("0")
        self.value_label.setObjectName("kpiValue")
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("kpiCaption")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DashboardView(QWidget):
    """At-a-glance summary of the whole scheduling system."""

    goToTimetable = Signal()
    goToImport = Signal()
    exportRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.controller = DashboardController()
        self._cards: dict[str, _KpiCard] = {}
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header row with title + quick actions.
        header = QHBoxLayout()
        title = QLabel("סקירה כללית")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)

        import_btn = QPushButton("ייבוא תלמידים")
        import_btn.setProperty("class", "secondary")
        import_btn.clicked.connect(self.goToImport.emit)
        header.addWidget(import_btn)

        auto_btn = QPushButton("מעבר לשיבוץ")
        auto_btn.clicked.connect(self.goToTimetable.emit)
        header.addWidget(auto_btn)

        export_btn = QPushButton("ייצוא מערכת")
        export_btn.setProperty("class", "secondary")
        export_btn.clicked.connect(self.exportRequested.emit)
        header.addWidget(export_btn)

        refresh_btn = QPushButton("רענון")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # KPI cards.
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)
        specs = [
            ("students", "תלמידים"),
            ("groups", "קבוצות לימוד"),
            ("tutors", "חונכות"),
            ("subjects", "מקצועות"),
            ("required", "שעות נדרשות"),
            ("assigned", "שעות שובצו"),
        ]
        for i, (key, caption) in enumerate(specs):
            card = _KpiCard(caption)
            self._cards[key] = card
            cards_grid.addWidget(card, 0, i)
        layout.addLayout(cards_grid)

        # Coverage progress.
        coverage_box = QGroupBox("כיסוי שיבוץ")
        coverage_layout = QVBoxLayout(coverage_box)
        self.coverage_caption = QLabel()
        coverage_layout.addWidget(self.coverage_caption)
        self.coverage_bar = QProgressBar()
        self.coverage_bar.setRange(0, 100)
        self.coverage_bar.setTextVisible(True)
        self.coverage_bar.setFormat("%p%")
        coverage_layout.addWidget(self.coverage_bar)
        layout.addWidget(coverage_box)

        # Two columns: tutor balance + action items.
        columns = QHBoxLayout()
        columns.setSpacing(16)

        balance_box = QGroupBox("איזון עומס בין החונכות")
        balance_outer = QVBoxLayout(balance_box)
        self.balance_caption = QLabel()
        balance_outer.addWidget(self.balance_caption)
        balance_scroll = QScrollArea()
        balance_scroll.setWidgetResizable(True)
        balance_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.balance_container = QWidget()
        self.balance_layout = QVBoxLayout(self.balance_container)
        self.balance_layout.setContentsMargins(0, 0, 0, 0)
        self.balance_layout.setSpacing(6)
        self.balance_layout.addStretch(1)
        balance_scroll.setWidget(self.balance_container)
        balance_outer.addWidget(balance_scroll, 1)
        columns.addWidget(balance_box, 1)

        pending_box = QGroupBox("דורש טיפול - ישויות שטרם שובצו במלואן")
        pending_layout = QVBoxLayout(pending_box)
        self.pending_list = QListWidget()
        pending_layout.addWidget(self.pending_list)
        columns.addWidget(pending_box, 1)

        layout.addLayout(columns, 1)

    # ----------------------------------------------------------------- render
    def _clear_balance(self) -> None:
        while self.balance_layout.count() > 1:  # keep the trailing stretch
            item = self.balance_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_balance(self, ov: Overview) -> None:
        self._clear_balance()
        max_hours = max((t.hours for t in ov.tutor_loads), default=0)
        bar_max = max(max_hours, 1)
        for tutor in ov.tutor_loads:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            name = QLabel(tutor.name if tutor.qualified else f"{tutor.name} ⚠")
            name.setMinimumWidth(120)
            if not tutor.qualified:
                name.setToolTip("לחונכת זו לא הוגדרו מקצועות - לא ניתן לשבץ לה")
            row_layout.addWidget(name)

            bar = QProgressBar()
            bar.setRange(0, bar_max)
            bar.setValue(tutor.hours)
            bar.setFormat(f"{tutor.hours} שעות")
            bar.setTextVisible(True)
            row_layout.addWidget(bar, 1)

            self.balance_layout.insertWidget(self.balance_layout.count() - 1, row)

        if ov.tutor_loads:
            self.balance_caption.setText(
                f"פער עומס: {ov.balance_spread} שעות "
                f"(מינימום {ov.min_load}, מקסימום {ov.max_load}). "
                f"{ov.tutors_unqualified} חונכות ללא מקצועות מוגדרים."
            )
        else:
            self.balance_caption.setText("אין חונכות עדיין.")

    def _render_pending(self, ov: Overview) -> None:
        self.pending_list.clear()
        if not ov.pending:
            item = QListWidgetItem("הכל משובץ - אין ישויות הממתינות לשיבוץ.")
            item.setForeground(Qt.GlobalColor.gray)
            self.pending_list.addItem(item)
            return
        for p in ov.pending:
            text = (
                f"{p.label}  [{p.subject_name}]  —  "
                f"שובץ {p.scheduled}/{p.required}  (חסר {p.missing})"
            )
            self.pending_list.addItem(QListWidgetItem(text))

    # --------------------------------------------------------------- refresh
    def refresh(self) -> None:
        ov = self.controller.get_overview()
        self._cards["students"].set_value(
            f"{ov.students_total}"
        )
        self._cards["students"].caption_label.setText(
            f"תלמידים ({ov.lone_students} בודדים, {ov.grouped_students} בקבוצות)"
        )
        self._cards["groups"].set_value(str(ov.groups_total))
        self._cards["tutors"].set_value(str(ov.tutors_total))
        self._cards["subjects"].set_value(str(ov.subjects_total))
        self._cards["required"].set_value(str(ov.required_hours))
        self._cards["assigned"].set_value(str(ov.assigned_hours))

        self.coverage_bar.setValue(ov.coverage_pct)
        self.coverage_caption.setText(
            f"{ov.assigned_hours} מתוך {ov.required_hours} שעות שבועיות שובצו."
        )
        self._render_balance(ov)
        self._render_pending(ov)
