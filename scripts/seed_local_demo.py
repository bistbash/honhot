#!/usr/bin/env python3
"""Populate the local app database with demo data.

Tutor qualifications and student enrollments match the tutoring leaflet (עלון
חונכות): only subjects the eight tutors can teach, realistic roster size, and
full grouping so auto-scheduling completes without gaps.

Usage:
    .venv/bin/python scripts/seed_local_demo.py --reset -y
    .venv/bin/python main.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repository root without installing the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.database as db
from app.config import (
    GRADE_TET,
    GRADE_YA,
    GRADE_YB,
    GRADE_YOD,
    GRADES,
    database_path,
)
from app.controllers.grouping_controller import GroupingController
from app.controllers.import_controller import ImportController
from app.controllers.schedule_controller import ScheduleController
from app.controllers.subject_controller import SubjectController
from app.controllers.tutor_controller import TutorController
from app.database import init_db, session_scope
from app.models import Student
from app.services.national_id import validate_national_id

# (name, grade, class_number)
PersonRow = tuple[str, str, int]
# (units, study_level)
Enrollment = tuple[int, int]

# ------------------------------------------------------------------ roster
# 24 students — realistic size for an eight-tutor centre.
ROSTER: list[PersonRow] = [
    # ט'
    ("דנה כהן", GRADE_TET, 1),
    ("יונתן לוי", GRADE_TET, 1),
    ("שירה בר", GRADE_TET, 2),
    ("איתי גולן", GRADE_TET, 2),
    ("נועה שמש", GRADE_TET, 3),
    ("עומר דהן", GRADE_TET, 3),
    # י'
    ("רון ישראלי", GRADE_YOD, 1),
    ("יעל מזרחי", GRADE_YOD, 1),
    ("תומר אור", GRADE_YOD, 2),
    ("הילה כץ", GRADE_YOD, 2),
    ("גיא מור", GRADE_YOD, 3),
    ("טלי נחום", GRADE_YOD, 3),
    # י"א
    ("מאיה ישראלי", GRADE_YA, 1),
    ("יוסי דוד", GRADE_YA, 1),
    ("רותם שפירא", GRADE_YA, 2),
    ("נועם שחר", GRADE_YA, 2),
    ("רון לוי", GRADE_YA, 3),
    ("עמית סגל", GRADE_YA, 3),
    # י"ב
    ("עידן שמיר", GRADE_YB, 1),
    ("ליאור בן שמואל", GRADE_YB, 1),
    ("יעל פרץ", GRADE_YB, 2),
    ("איתי קרמר", GRADE_YB, 2),
    ("נועה בר", GRADE_YB, 3),
    ("מיכל שפירא", GRADE_YB, 3),
]

# Fixed, checksum-valid national IDs — one per person (stable across subjects).
NATIONAL_IDS: dict[str, str] = {
    "דנה כהן": "100000017",
    "יונתן לוי": "100000272",
    "שירה בר": "100000306",
    "איתי גולן": "100000561",
    "נועה שמש": "100000595",
    "עומר דהן": "100000629",
    "רון ישראלי": "100000850",
    "יעל מזרחי": "100000884",
    "תומר אור": "100000918",
    "הילה כץ": "100001122",
    "גיא מור": "100001411",
    "טלי נחום": "100001445",
    "מאיה ישראלי": "100001700",
    "יוסי דוד": "100001734",
    "רותם שפירא": "100002278",
    "נועם שחר": "100002567",
    "רון לוי": "100002856",
    "עמית סגל": "100003060",
    "עידן שמיר": "100003094",
    "ליאור בן שמואל": "100003128",
    "יעל פרץ": "100003383",
    "איתי קרמר": "100003417",
    "נועה בר": "100003672",
    "מיכל שפירא": "100003706",
}

assert set(NATIONAL_IDS) == {name for name, _, _ in ROSTER}
for _name, _nid in NATIONAL_IDS.items():
    validate_national_id(_nid)

# Per-subject enrollments: name -> (units, study_level).
# Only subjects/grades covered by at least one tutor on the flyer.
# Bucket sizes are multiples of 2–4 so every student can be grouped.
MATH_ENROLL: dict[str, Enrollment] = {
    # ט' — 3 יח"ל
    "דנה כהן": (3, 3),
    "יונתן לוי": (3, 3),
    "שירה בר": (3, 3),
    "איתי גולן": (3, 3),
    "נועה שמש": (3, 3),
    "עומר דהן": (3, 3),
    # י' — 3 יח"ל
    "רון ישראלי": (3, 3),
    "יעל מזרחי": (3, 3),
    "תומר אור": (3, 3),
    "הילה כץ": (3, 3),
    "גיא מור": (3, 3),
    "טלי נחום": (3, 3),
    # י"א — 5 יח"ל (ליה / נועם / אביגיל)
    "מאיה ישראלי": (5, 4),
    "יוסי דוד": (5, 4),
    "רותם שפירא": (5, 4),
    "נועם שחר": (5, 4),
    # י"א — 3 יח"ל
    "רון לוי": (3, 3),
    "עמית סגל": (3, 3),
    # י"ב — 4 יח"ל (חן / ליה)
    "עידן שמיר": (4, 4),
    "ליאור בן שמואל": (4, 4),
    "יעל פרץ": (4, 4),
    "איתי קרמר": (4, 4),
    # י"ב — 3 יח"ל
    "נועה בר": (3, 3),
    "מיכל שפירא": (3, 3),
}

ENGLISH_ENROLL: dict[str, Enrollment] = {
    # ט' — אנגלית (כל החונכות חוץ מחן שמוגבלת לט')
    "דנה כהן": (3, 3),
    "שירה בר": (3, 3),
    "נועה שמש": (3, 3),
    "איתי גולן": (3, 3),
    # י'
    "רון ישראלי": (3, 3),
    "יעל מזרחי": (3, 3),
    "תומר אור": (3, 3),
    "הילה כץ": (3, 3),
    "גיא מור": (3, 3),
    "טלי נחום": (3, 3),
    # י"א — עד 4 יח"ל (אדר מוגבלת ל-4)
    "מאיה ישראלי": (4, 4),
    "יוסי דוד": (4, 4),
    "רותם שפירא": (4, 3),
    "נועם שחר": (4, 3),
    "רון לוי": (4, 4),
    "עמית סגל": (4, 3),
    # י"ב
    "עידן שמיר": (4, 4),
    "ליאור בן שמואל": (4, 3),
    "יעל פרץ": (4, 3),
    "איתי קרמר": (4, 4),
    "נועה בר": (4, 3),
    "מיכל שפירא": (4, 4),
}

# היסטוריה: ט'–י"א בלבד (אין חונכת לי"ב)
HISTORY_ENROLL: dict[str, Enrollment] = {
    "דנה כהן": (2, 3),
    "יונתן לוי": (2, 3),
    "שירה בר": (2, 3),
    "רון ישראלי": (3, 3),
    "יעל מזרחי": (3, 3),
    "תומר אור": (3, 3),
    "הילה כץ": (3, 3),
    "מאיה ישראלי": (3, 3),
    "יוסי דוד": (3, 3),
    "רותם שפירא": (3, 3),
    "נועם שחר": (3, 3),
}

# פיזיקה: ט' בלבד (עומר)
PHYSICS_ENROLL: dict[str, Enrollment] = {
    "עומר דהן": (3, 3),
    "איתי גולן": (3, 3),
    "נועה שמש": (3, 3),
}

LITERATURE_ENROLL: dict[str, Enrollment] = {
    "רון ישראלי": (3, 3),
    "יעל מזרחי": (3, 3),
    "תומר אור": (3, 3),
    "מאיה ישראלי": (3, 4),
    "יוסי דוד": (3, 4),
    "רותם שפירא": (3, 3),
    "נועם שחר": (3, 3),
    "עידן שמיר": (3, 4),
    "ליאור בן שמואל": (3, 4),
    "יעל פרץ": (3, 3),
    "איתי קרמר": (3, 3),
    "נועה בר": (3, 3),
}

TANACH_ENROLL: dict[str, Enrollment] = {
    "דנה כהן": (2, 3),
    "יונתן לוי": (2, 3),
    "שירה בר": (2, 3),
    "איתי גולן": (2, 3),
    "רון ישראלי": (2, 3),
    "יעל מזרחי": (2, 3),
    "תומר אור": (2, 3),
    "הילה כץ": (2, 3),
    "מאיה ישראלי": (2, 3),
    "יוסי דוד": (2, 3),
    "רותם שפירא": (2, 3),
    "נועם שחר": (2, 3),
}

CIVICS_ENROLL: dict[str, Enrollment] = {
    "רון ישראלי": (2, 3),
    "יעל מזרחי": (2, 3),
    "תומר אור": (2, 3),
    "הילה כץ": (2, 3),
    "מאיה ישראלי": (2, 3),
    "יוסי דוד": (2, 3),
    "רותם שפירא": (2, 3),
    "נועם שחר": (2, 3),
    "עידן שמיר": (2, 3),
    "ליאור בן שמואל": (2, 3),
    "יעל פרץ": (2, 3),
    "איתי קרמר": (2, 3),
}

HEBREW_ENROLL: dict[str, Enrollment] = {
    "דנה כהן": (2, 3),
    "יונתן לוי": (2, 3),
    "שירה בר": (2, 3),
    "איתי גולן": (2, 3),
    "רון ישראלי": (2, 3),
    "יעל מזרחי": (2, 3),
    "תומר אור": (2, 3),
    "הילה כץ": (2, 3),
    "מאיה ישראלי": (2, 3),
    "יוסי דוד": (2, 3),
}

# ------------------------------------------------------------------ tutors (עלון חונכות)
# (name, [(subject_key, grades, units_min, units_max)], blocked_cells)
TutorSpec = tuple[str, list[tuple[str, list[str], int, int]], set[tuple[int, int]]]

TUTOR_SPECS: list[TutorSpec] = [
    (
        "חן",
        [
            ("math", GRADES, 3, 4),
            ("civics", [GRADE_YA, GRADE_YB], 2, 5),
            ("literature", [GRADE_YB], 3, 5),
            ("english", [GRADE_TET], 3, 5),
        ],
        set(),
    ),
    (
        "עומר",
        [
            ("math", [GRADE_TET, GRADE_YOD], 3, 4),
            ("english", GRADES, 3, 5),
            ("history", [GRADE_TET, GRADE_YOD, GRADE_YA], 2, 5),
            ("hebrew", [GRADE_TET], 2, 5),
            ("physics", [GRADE_TET], 3, 5),
        ],
        set(),
    ),
    (
        "נעמה",
        [
            ("english", GRADES, 3, 5),
            ("civics", [GRADE_YOD, GRADE_YA, GRADE_YB], 2, 5),
            ("history", [GRADE_TET, GRADE_YOD, GRADE_YA], 2, 5),
            ("tanach", [GRADE_TET, GRADE_YOD, GRADE_YA], 2, 3),
            ("literature", [GRADE_YOD, GRADE_YA, GRADE_YB], 3, 5),
            ("hebrew", [GRADE_TET, GRADE_YOD, GRADE_YA], 2, 5),
        ],
        set(),
    ),
    (
        "אדר",
        [
            ("english", GRADES, 3, 4),
            ("tanach", [GRADE_TET, GRADE_YOD, GRADE_YA], 2, 3),
            ("literature", [GRADE_YOD, GRADE_YA, GRADE_YB], 3, 5),
        ],
        set(),
    ),
    (
        "נועם",
        [
            ("english", GRADES, 3, 5),
            ("math", [GRADE_TET, GRADE_YOD], 3, 5),
            ("civics", [GRADE_YOD, GRADE_YA, GRADE_YB], 2, 5),
            ("hebrew", [GRADE_TET], 2, 5),
        ],
        set(),
    ),
    (
        "ים",
        [
            ("english", GRADES, 3, 5),
            ("math", [GRADE_TET], 3, 3),
            ("math", [GRADE_YOD, GRADE_YA, GRADE_YB], 3, 3),
            ("hebrew", [GRADE_TET, GRADE_YOD, GRADE_YA], 2, 5),
            ("history", [GRADE_YOD, GRADE_YA], 2, 5),
            ("civics", [GRADE_YOD, GRADE_YA, GRADE_YB], 2, 5),
        ],
        set(),
    ),
    (
        "אביגיל",
        [
            ("english", GRADES, 3, 5),
            ("math", [GRADE_TET, GRADE_YOD], 3, 5),
        ],
        set(),
    ),
    (
        "ליה",
        [
            ("math", GRADES, 3, 5),
            ("literature", [GRADE_YOD, GRADE_YA], 3, 5),
            ("tanach", [GRADE_YOD, GRADE_YA], 2, 3),
        ],
        set(),
    ),
]

# Preferred tutor by person name — only where the tutor is qualified.
PREFERRED_TUTOR_BY_PERSON: dict[str, str] = {
    "דנה כהן": "נעמה",
    "מאיה ישראלי": "ליה",
    "יוסי דוד": "ליה",
    "רון לוי": "נעמה",
    "עידן שמיר": "חן",
    "יעל פרץ": "אדר",
    "נועה בר": "נעמה",
    "רותם שפירא": "נועם",
    "תומר אור": "ים",
}

# Manual groups: (subject_key, group_name, member_names, preferred_tutor_name)
MANUAL_GROUPS: list[tuple[str, str, list[str], str | None]] = [
    (
        "math",
        "חיזוק י\"א - 5 יח\"ל",
        ["מאיה ישראלי", "יוסי דוד", "רותם שפירא", "נועם שחר"],
        "ליה",
    ),
    (
        "english",
        "אנגלית מתקדמים י\"ב",
        ["יעל פרץ", "איתי קרמר", "נועה בר", "ליאור בן שמואל"],
        "אדר",
    ),
    (
        "history",
        "היסטוריה י' - קבוצה א'",
        ["רון ישראלי", "יעל מזרחי", "תומר אור", "הילה כץ"],
        "נעמה",
    ),
]

# Subject time windows and weekly hours.
SUBJECT_CONFIG: dict[str, dict] = {
    "math": {
        "name": "מתמטיקה",
        "weekly_hours": 2,
        "windows": {(day, hour) for day in range(5) for hour in (1, 2, 3, 4, 5, 7, 8)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": {
            "מאיה ישראלי",
            "יוסי דוד",
            "רותם שפירא",
            "נועם שחר",
        },
    },
    "english": {
        "name": "אנגלית",
        "weekly_hours": 2,
        "windows": {(day, hour) for day in range(5) for hour in (2, 3, 4, 5, 7, 8, 9)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": {
            "יעל פרץ",
            "איתי קרמר",
            "נועה בר",
            "ליאור בן שמואל",
        },
    },
    "history": {
        "name": "היסטוריה",
        "weekly_hours": 2,
        "windows": {(day, hour) for day in range(5) for hour in (0, 1, 2, 7, 8, 9)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": {
            "רון ישראלי",
            "יעל מזרחי",
            "תומר אור",
            "הילה כץ",
        },
    },
    "physics": {
        "name": "פיזיקה",
        "weekly_hours": 2,
        "windows": {(day, hour) for day in (0, 2, 4) for hour in (7, 8, 9)},
        "auto_group_max_size": 3,
        "skip_auto_group_names": set(),
    },
    "literature": {
        "name": "ספרות",
        "weekly_hours": 2,
        "windows": {(day, hour) for day in range(5) for hour in (3, 4, 5, 7, 8, 9)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": set(),
    },
    "tanach": {
        "name": "תנ\"ך",
        "weekly_hours": 1,
        "windows": {(day, hour) for day in range(5) for hour in (0, 1, 2, 7, 8)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": set(),
    },
    "civics": {
        "name": "אזרחות",
        "weekly_hours": 2,
        "windows": {(day, hour) for day in range(5) for hour in (0, 1, 7, 8, 9)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": set(),
    },
    "hebrew": {
        "name": "עברית",
        "weekly_hours": 1,
        "windows": {(day, hour) for day in range(5) for hour in (0, 1, 2, 7, 8)},
        "auto_group_max_size": 4,
        "skip_auto_group_names": set(),
    },
}

GLOBAL_BREAK = {(day, 6) for day in range(6)}

ENROLLMENTS_BY_KEY: dict[str, dict[str, Enrollment]] = {
    "math": MATH_ENROLL,
    "english": ENGLISH_ENROLL,
    "history": HISTORY_ENROLL,
    "physics": PHYSICS_ENROLL,
    "literature": LITERATURE_ENROLL,
    "tanach": TANACH_ENROLL,
    "civics": CIVICS_ENROLL,
    "hebrew": HEBREW_ENROLL,
}


def _confirm_reset() -> bool:
    path = database_path()
    if not path.exists():
        return True
    print(f"מסד הנתונים הקיים יימחק: {path}")
    answer = input("להמשיך? [y/N] ").strip().lower()
    return answer in {"y", "yes", "כ", "כן"}


def clear_database(*, skip_confirm: bool = False) -> None:
    """Delete the local SQLite file and re-initialise an empty schema."""
    if not skip_confirm and not _confirm_reset():
        print("בוטל.")
        sys.exit(0)

    path = database_path()
    if path.exists():
        path.unlink()

    db._engine = None
    db._SessionFactory = None
    init_db()


def _roster_by_name() -> dict[str, PersonRow]:
    return {name: (name, grade, cls) for name, grade, cls in ROSTER}


def _national_id_for_name(name: str) -> str:
    """Return the demo national ID for a roster name."""
    try:
        return NATIONAL_IDS[name]
    except KeyError as exc:
        raise KeyError(f"חסרה ת.ז. לדוגמה עבור '{name}'") from exc


def _add_students(subject_id: int, enroll: dict[str, Enrollment]) -> dict[str, int]:
    """Insert students; return name -> student_id."""
    roster = _roster_by_name()
    name_to_id: dict[str, int] = {}
    with session_scope() as session:
        for name, (units, level) in enroll.items():
            person = roster.get(name)
            if person is None:
                continue
            _, grade, class_number = person
            student = Student(
                name=name,
                national_id=_national_id_for_name(name),
                grade=grade,
                class_number=class_number,
                units=units,
                study_level=level,
                subject_id=subject_id,
            )
            session.add(student)
            session.flush()
            name_to_id[name] = student.id
    return name_to_id


def _apply_preferred_tutors(
    tutor_name_to_id: dict[str, int],
    student_maps: dict[str, dict[str, int]],
) -> int:
    import_ctrl = ImportController()
    count = 0
    for person_name, tutor_name in PREFERRED_TUTOR_BY_PERSON.items():
        tutor_id = tutor_name_to_id.get(tutor_name)
        if tutor_id is None:
            continue
        for subject_key, name_to_id in student_maps.items():
            student_id = name_to_id.get(person_name)
            if student_id is None:
                continue
            import_ctrl.set_student_preferred_tutor(student_id, tutor_id)
            count += 1
    return count


def _create_auto_groups(
    subject_key: str,
    subject_id: int,
    skip_names: set[str],
) -> int:
    grouping = GroupingController()
    max_size = SUBJECT_CONFIG[subject_key]["auto_group_max_size"]
    suggestions = grouping.suggestions_for_subject(subject_id, max_size=max_size)
    created = 0
    for suggestion in suggestions:
        member_names = {m.name for m in suggestion.members}
        if member_names & skip_names:
            continue
        grouping.create_group(subject_id, suggestion)
        created += 1
    return created


def _create_manual_groups(
    subject_key: str,
    subject_id: int,
    name_to_id: dict[str, int],
    tutor_name_to_id: dict[str, int],
) -> int:
    grouping = GroupingController()
    created = 0
    for key, group_name, members, preferred_name in MANUAL_GROUPS:
        if key != subject_key:
            continue
        ids = [name_to_id[n] for n in members if n in name_to_id]
        if len(ids) < 2:
            continue
        preferred_id = (
            tutor_name_to_id.get(preferred_name) if preferred_name else None
        )
        grouping.create_manual_group(
            subject_id,
            group_name,
            ids,
            preferred_tutor_id=preferred_id,
        )
        created += 1
    return created


def _group_all_remaining(subject_id: int, max_size: int = 4) -> int:
    """Batch any leftover ungrouped students into manual groups."""
    grouping = GroupingController()
    created = 0
    while True:
        ungrouped = grouping.list_ungrouped_students(subject_id)
        if not ungrouped:
            break
        buckets: dict[tuple[str, int], list[dict]] = {}
        for student in ungrouped:
            key = (student["grade"], student["units"])
            buckets.setdefault(key, []).append(student)
        progress = False
        for key, members in sorted(buckets.items()):
            if len(members) < 2:
                continue
            chunk = members[:max_size]
            grade, units = key
            level = chunk[0]["study_level"]
            name = f"קבוצה {grade} · {units} יח\"ל · רמה {level}"
            grouping.create_manual_group(
                subject_id, name, [m["id"] for m in chunk]
            )
            created += 1
            progress = True
            break
        if not progress:
            break
    return created


def _set_group_preferred_tutors(
    subject_ids: dict[str, int],
    tutor_name_to_id: dict[str, int],
    manual_group_names: set[str],
) -> int:
    """Assign preferred tutors to the first auto-created group per major subject."""
    grouping = GroupingController()
    prefs = {
        "math": "נועם",
        "english": "נעמה",
        "physics": "עומר",
    }
    count = 0
    for key, tutor_name in prefs.items():
        sid = subject_ids.get(key)
        tid = tutor_name_to_id.get(tutor_name)
        if sid is None or tid is None:
            continue
        for group in grouping.list_groups(sid):
            if group["name"] in manual_group_names:
                continue
            grouping.set_group_details(
                group["id"], group["name"], preferred_tutor_id=tid
            )
            count += 1
            break
    return count


def seed_demo_data() -> dict[str, object]:
    """Populate subjects, students, tutors, groups and run auto-assign."""
    subject_ctrl = SubjectController()
    tutor_ctrl = TutorController()
    schedule_ctrl = ScheduleController()

    subject_ids: dict[str, int] = {}
    for key, cfg in SUBJECT_CONFIG.items():
        sid = subject_ctrl.add_subject(cfg["name"])
        subject_ids[key] = sid
        if cfg["weekly_hours"] is not None:
            subject_ctrl.set_weekly_hours(sid, cfg["weekly_hours"])
        if cfg.get("windows"):
            subject_ctrl.set_windows(sid, cfg["windows"])

    student_maps: dict[str, dict[str, int]] = {}
    student_counts: dict[str, int] = {}
    for key, enroll in ENROLLMENTS_BY_KEY.items():
        sid = subject_ids[key]
        name_to_id = _add_students(sid, enroll)
        student_maps[key] = name_to_id
        student_counts[key] = len(name_to_id)

    tutor_name_to_id: dict[str, int] = {}
    for name, quals, blocked in TUTOR_SPECS:
        tutor_id = tutor_ctrl.add_tutor(name)
        tutor_name_to_id[name] = tutor_id
        if blocked:
            tutor_ctrl.set_unavailability(tutor_id, blocked)
        for subject_key, grades, u_min, u_max in quals:
            sid = subject_ids[subject_key]
            tutor_ctrl.add_tutor_subject(tutor_id, sid, grades, u_min, u_max)

    tutor_ctrl.set_global_unavailability(GLOBAL_BREAK)

    preferred_count = _apply_preferred_tutors(tutor_name_to_id, student_maps)

    manual_group_names = {name for _, name, _, _ in MANUAL_GROUPS}

    group_counts: dict[str, int] = {}
    manual_group_counts: dict[str, int] = {}
    for key, sid in subject_ids.items():
        skip = SUBJECT_CONFIG[key].get("skip_auto_group_names", set())
        manual_group_counts[key] = _create_manual_groups(
            key, sid, student_maps[key], tutor_name_to_id
        )
        group_counts[key] = _create_auto_groups(key, sid, skip)
        max_size = SUBJECT_CONFIG[key]["auto_group_max_size"]
        _group_all_remaining(sid, max_size=max_size)

    extra_group_prefs = _set_group_preferred_tutors(
        subject_ids, tutor_name_to_id, manual_group_names
    )

    summary = schedule_ctrl.auto_assign(clear_existing=True)

    total_students = sum(student_counts.values())
    total_groups = sum(group_counts.values()) + sum(manual_group_counts.values())

    return {
        "subject_ids": subject_ids,
        "student_counts": student_counts,
        "total_students": total_students,
        "tutors": len(tutor_name_to_id),
        "group_counts": group_counts,
        "manual_group_counts": manual_group_counts,
        "total_groups": total_groups,
        "preferred_student_links": preferred_count,
        "extra_group_prefs": extra_group_prefs,
        "assigned": summary.assigned,
        "unassigned": summary.unassigned_labels,
        "tutor_loads": summary.tutor_loads,
        "db_path": database_path(),
        "roster_size": len(ROSTER),
        "national_ids": dict(NATIONAL_IDS),
    }


def _print_summary(result: dict[str, object]) -> None:
    print()
    print("נתוני הדמה נטענו בהצלחה.")
    print(f"  מסד נתונים: {result['db_path']}")
    print(f"  תלמידים ייחודיים: {result['roster_size']}")
    print(f"  סה\"כ רשומות תלמיד (לפי מקצוע): {result['total_students']}")
    print("  מקצועות:")
    subject_ids: dict[str, int] = result["subject_ids"]  # type: ignore[assignment]
    student_counts: dict[str, int] = result["student_counts"]  # type: ignore[assignment]
    group_counts: dict[str, int] = result["group_counts"]  # type: ignore[assignment]
    manual_counts: dict[str, int] = result["manual_group_counts"]  # type: ignore[assignment]
    for key, sid in subject_ids.items():
        cfg = SUBJECT_CONFIG[key]
        auto_g = group_counts.get(key, 0)
        manual_g = manual_counts.get(key, 0)
        print(
            f"    - {cfg['name']} (id={sid}): "
            f"{student_counts[key]} תלמידים, "
            f"{auto_g} קבוצות אוטומטיות + {manual_g} ידניות, "
            f"{cfg['weekly_hours']} ש\"ש"
        )
    print(f"  חונכות: {result['tutors']} (מעלון חונכות)")
    for name, hours in result["tutor_loads"]:
        print(f"    - {name}: {hours} שעות")
    print(f"  קבוצות: {result['total_groups']}")
    print(
        f"  העדפות חונכת: {result['preferred_student_links']} תלמידים, "
        f"{result['extra_group_prefs']} קבוצות"
    )
    print(f"  שיבוץ אוטומטי: {result['assigned']} שעות")
    unassigned: list[str] = result["unassigned"]  # type: ignore[assignment]
    if unassigned:
        print(f"  לא שובצו ({len(unassigned)}): {', '.join(unassigned[:8])}")
        if len(unassigned) > 8:
            print(f"    ... ועוד {len(unassigned) - 8}")
    else:
        print("  שיבוץ מלא — כל הקבוצות והתלמידים שובצו")
    national_ids: dict[str, str] = result["national_ids"]  # type: ignore[assignment]
    print()
    print("  ת.ז. לדוגמה (לחיפוש ב-HTML / זיהוי תלמידים עם אותו שם פרטי):")
    samples = [
        ("דנה כהן", "רשומה במספר מקצועות — אותה ת.ז."),
        ("רון ישראלי", "לא לבלבל עם רון לוי"),
        ("רון לוי", f"ת.ז. {national_ids['רון לוי']}"),
        ("יעל מזרחי", "לא לבלבל עם יעל פרץ"),
    ]
    for name, note in samples:
        print(f"    - {name}: {national_ids[name]}  ({note})")
    print("    (רשימה מלאה ב-NATIONAL_IDS בקובץ seed_local_demo.py)")
    print()
    print("הפעל את האפליקציה:")
    print("  .venv/bin/python main.py")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="טעינת נתוני דמה לוקליים למערכת שעות לחונכות"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="מחק את מסד הנתונים המקומי לפני הטעינה (ברירת מחדל)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="הוסף דמה על מסד קיים (עלול ליצור כפילויות)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="אשר מחיקת DB ללא שאלה",
    )
    args = parser.parse_args()

    do_reset = args.reset or not args.no_reset
    if do_reset:
        clear_database(skip_confirm=args.yes)
    else:
        init_db()

    result = seed_demo_data()
    _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
