# מערכת שעות לחונכות — Tutoring Scheduler

תוכנת שולחן עבודה (offline) לניהול מערכת שעות של חונכות: ייבוא מקצועות מאקסל,
חלוקה חכמה לקבוצות לימוד, שיבוץ אינטראקטיבי בגרירה לכל חונכת, ושריון זמנים
למקצועות. ממשק עברי מלא בכיוון ימין-לשמאל.

An offline Windows desktop application for managing a tutoring/mentoring
timetable. Built with Python + PySide6, SQLite/SQLAlchemy and Pandas.

## Features

- **ייבוא אקסל** — import a subject's students from `.xlsx`. Required columns:
  `שם תלמיד`, `כיתה`, `יח"ל`, `רמת לימוד`. The `כיתה` token (e.g. `י"ב4`, `ט'1`)
  is parsed into a grade (`שכבה`) and a class number, with per-row validation and
  professional error dialogs.
- **קבוצות לימוד** — a smart engine suggests groups of students that share the
  same grade, units and study level; merge them into formal study groups.
- **חונכות** — manage tutors, including enabling/disabling (נטרול) them.
- **שריון מקצועות** — reserve the specific day/hour cells in which a subject may
  be scheduled (e.g. math only on Tuesday).
- **מערכת שעות** — an interactive weekly grid (Sunday–Friday × hours 0–10) with
  drag & drop from a sidebar of students and groups. Drops are validated:
  the tutor must be active, the slot must be free, the entity must not clash at
  the same time elsewhere, and reserved-window rules are enforced.
- **ייצוא** — export the whole system or a single tutor to Excel or PDF.
- Light/dark theme toggle.

## Architecture

Layered MVC, keeping Qt out of the business logic:

```
app/
  models/        SQLAlchemy ORM models (data)
  services/      pure business logic (Excel parsing, grouping, export)
  controllers/   coordinate views, services and the DB session
  views/         PySide6 UI (Qt only)
```

The SQLite database is stored per-user at
`%LOCALAPPDATA%\TutoringScheduler\schedule.db`.

## Requirements

- Python 3.11+ (developed and tested on 3.13).

## Setup & Run (from source)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Tests

```bash
set QT_QPA_PLATFORM=offscreen   # PowerShell: $env:QT_QPA_PLATFORM="offscreen"
pytest -q
```

## Build a standalone .exe

```bash
pip install pyinstaller
pyinstaller build.spec
```

The packaged application is created under `dist/TutoringScheduler/`. Launch
`TutoringScheduler.exe`.

## Importing data — column reference

| Excel column | Meaning            | Notes                                   |
|--------------|--------------------|-----------------------------------------|
| `שם תלמיד`   | Student name       | required                                |
| `כיתה`       | Grade + class      | e.g. `ט1`, `יא2`, `י"ב4`, `י'1`          |
| `יח"ל`       | Units              | integer 1–5                             |
| `רמת לימוד`  | Study level        | integer 1–5                             |

Each file represents one subject; you are prompted for the subject name on
import.
