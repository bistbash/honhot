"""Israeli national ID (תעודת זהות) normalization and validation."""

from __future__ import annotations

import re


def normalize_national_id(raw: str) -> str:
    """Strip non-digits and pad to 9 digits."""
    digits = re.sub(r"\D", "", raw.strip())
    if not digits:
        raise ValueError("יש להזין תעודת זהות")
    if len(digits) > 9:
        raise ValueError("תעודת זהות לא תקינה")
    return digits.zfill(9)


def validate_national_id(raw: str) -> str:
    """Return a normalized 9-digit ID or raise ``ValueError``."""
    national_id = normalize_national_id(raw)
    if not national_id.isdigit():
        raise ValueError("תעודת זהות חייבת להכיל ספרות בלבד")

    total = 0
    for index, digit in enumerate(national_id):
        value = int(digit) * (1 if index % 2 == 0 else 2)
        if value > 9:
            value -= 9
        total += value
    if total % 10 != 0:
        raise ValueError("תעודת זהות לא תקינה (ספרת ביקורת)")
    return national_id
