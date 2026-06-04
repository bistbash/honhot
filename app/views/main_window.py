"""Application main window: hosts the feature tabs and global actions."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.views.theme import Theme, apply_theme


class MainWindow(QMainWindow):
    """Top-level window with a tabbed workflow and a global toolbar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  -  v{APP_VERSION}")
        self.resize(1280, 820)
        self._theme = Theme.LIGHT

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        self._build_pages()
        self._build_toolbar()
        self.statusBar().showMessage("מוכן")

    # ------------------------------------------------------------------ pages
    def _build_pages(self) -> None:
        """Instantiate and register the feature views as tabs."""
        from app.views.dashboard_view import DashboardView
        from app.views.import_view import ImportView
        from app.views.grouping_view import GroupingView
        from app.views.subject_view import SubjectView
        from app.views.timetable.timetable_view import TimetableView
        from app.views.tutor_view import TutorView

        self.dashboard_view = DashboardView()
        self.import_view = ImportView()
        self.grouping_view = GroupingView()
        self.tutor_view = TutorView()
        self.subject_view = SubjectView()
        self.timetable_view = TimetableView()

        self.tabs.addTab(self.dashboard_view, "סקירה")
        self.tabs.addTab(self.import_view, "ייבוא ותלמידים")
        self.tabs.addTab(self.grouping_view, "קבוצות לימוד")
        self.tabs.addTab(self.tutor_view, "חונכות")
        self.tabs.addTab(self.subject_view, "שריון מקצועות")
        self.tabs.addTab(self.timetable_view, "מערכת שעות")

        # Dashboard quick-action navigation.
        self.dashboard_view.goToImport.connect(
            lambda: self.tabs.setCurrentWidget(self.import_view)
        )
        self.dashboard_view.goToTimetable.connect(
            lambda: self.tabs.setCurrentWidget(self.timetable_view)
        )
        self.dashboard_view.exportRequested.connect(self._on_export)

        # Refresh dependent views when switching tabs so data stays in sync.
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, _index: int) -> None:
        widget = self.tabs.currentWidget()
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()

    # ---------------------------------------------------------------- toolbar
    def _build_toolbar(self) -> None:
        toolbar = QToolBar("ראשי")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        title = QLabel(f"  {APP_NAME}  ")
        title.setObjectName("appTitle")
        toolbar.addWidget(title)
        toolbar.addSeparator()

        export_action = QAction("ייצוא מערכת", self)
        export_action.triggered.connect(self._on_export)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        self.theme_action = QAction("מצב כהה", self)
        self.theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self.theme_action)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(spacer)

        about_action = QAction("אודות", self)
        about_action.triggered.connect(self._show_about)
        toolbar.addAction(about_action)

    # ----------------------------------------------------------------- slots
    def _toggle_theme(self) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        self._theme = Theme.DARK if self._theme == Theme.LIGHT else Theme.LIGHT
        apply_theme(app, self._theme)
        self.theme_action.setText(
            "מצב בהיר" if self._theme == Theme.DARK else "מצב כהה"
        )

    def _on_export(self) -> None:
        from app.controllers.export_controller import ExportController

        ExportController(self).open_export_dialog()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "אודות",
            f"<b>{APP_NAME}</b><br>גרסה {APP_VERSION}<br><br>"
            "תוכנה לניהול מערכת שעות של חונכות.",
        )
