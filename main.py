"""Entry point for the Tutoring Scheduler desktop application."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, ORG_NAME
from app.database import init_db
from app.views.main_window import MainWindow
from app.views.theme import Theme, apply_theme


def main() -> int:
    """Configure the application, build the database and show the main window."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    # Hebrew UI: render the whole application right-to-left.
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    apply_theme(app, Theme.LIGHT)

    init_db()

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
