"""Offscreen smoke test: build the main window and seed sample data."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.database import init_db
from app.views.main_window import MainWindow
from app.views.theme import Theme, apply_theme


def run() -> None:
    app = QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    apply_theme(app, Theme.LIGHT)
    init_db()
    window = MainWindow()
    window.show()
    app.processEvents()
    # Exercise theme toggle and tab switching.
    window._toggle_theme()
    for i in range(window.tabs.count()):
        window.tabs.setCurrentIndex(i)
        app.processEvents()
    print("SMOKE OK: built window with", window.tabs.count(), "tabs")


if __name__ == "__main__":
    run()
