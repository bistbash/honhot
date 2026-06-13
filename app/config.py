"""Application-wide constants and path helpers.

This module is intentionally free of any Qt or SQLAlchemy imports so that it can
be safely imported from any layer (models, services, controllers, views).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

APP_NAME: Final[str] = "מערכת שעות לחונכות"
APP_VERSION: Final[str] = "1.0.0"
ORG_NAME: Final[str] = "TutoringScheduler"

# --- Schedule grid definition -------------------------------------------------
# Days of the week, indexed 0..5 (Sunday..Friday). In an RTL layout the first
# day (ראשון) is rendered on the right-hand side automatically by Qt.
DAYS: Final[list[str]] = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי"]

# Lesson hours 0..10 inclusive (11 rows).
HOUR_MIN: Final[int] = 0
HOUR_MAX: Final[int] = 10
HOURS: Final[list[int]] = list(range(HOUR_MIN, HOUR_MAX + 1))

# Soft preference for auto-scheduler: avoid tutor teaching streaks longer than this.
TUTOR_PREFERRED_MAX_CONSECUTIVE: Final[int] = 2

# --- Student domain values ----------------------------------------------------
# Canonical grade labels (שכבה) with correct gershayim/geresh punctuation.
GRADE_TET: Final[str] = "ט'"
GRADE_YOD: Final[str] = "י'"
GRADE_YA: Final[str] = 'י"א'
GRADE_YB: Final[str] = 'י"ב'
GRADES: Final[list[str]] = [GRADE_TET, GRADE_YOD, GRADE_YA, GRADE_YB]

UNITS_MIN: Final[int] = 1
UNITS_MAX: Final[int] = 5
LEVEL_MIN: Final[int] = 1
LEVEL_MAX: Final[int] = 5

# --- Excel import column headers (Hebrew) ------------------------------------
COL_NAME: Final[str] = "שם תלמיד"
COL_CLASS: Final[str] = "כיתה"
COL_UNITS: Final[str] = 'יח"ל'
COL_LEVEL: Final[str] = "רמת לימוד"
REQUIRED_COLUMNS: Final[list[str]] = [COL_NAME, COL_CLASS, COL_UNITS, COL_LEVEL]

# --- Drag & drop MIME type ----------------------------------------------------
ENTITY_MIME_TYPE: Final[str] = "application/x-tutoring-entity"


def app_data_dir() -> Path:
    """Return a writable directory for the SQLite database and user data.

    When frozen by PyInstaller we cannot write next to the executable reliably,
    so we use the per-user application data directory instead.
    """
    base = Path.home() / "AppData" / "Local" / ORG_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_dir() -> Path:
    """Return the directory containing bundled resources (styles, icons).

    Works both when running from source and when frozen by PyInstaller, which
    unpacks data files into ``sys._MEIPASS``.
    """
    if getattr(sys, "frozen", False):  # pragma: no cover - only when packaged
        return Path(getattr(sys, "_MEIPASS")) / "app" / "resources"
    return Path(__file__).resolve().parent / "resources"


def database_path() -> Path:
    """Return the absolute path to the SQLite database file."""
    return app_data_dir() / "schedule.db"
