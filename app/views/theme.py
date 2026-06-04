"""Theme loading and toggling helpers (light/dark QSS)."""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QApplication

from app.config import resource_dir


class Theme(str, Enum):
    """Available UI themes."""

    LIGHT = "light"
    DARK = "dark"


def load_stylesheet(theme: Theme) -> str:
    """Read the QSS stylesheet for the given theme, or empty string if missing."""
    path = resource_dir() / "styles" / f"{theme.value}.qss"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Apply the given theme's stylesheet to the whole application."""
    app.setStyleSheet(load_stylesheet(theme))
