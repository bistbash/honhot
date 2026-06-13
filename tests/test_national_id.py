"""Tests for Israeli national ID validation."""

from __future__ import annotations

import pytest

from app.services.national_id import normalize_national_id, validate_national_id


def test_normalize_strips_non_digits() -> None:
    assert normalize_national_id("123456782") == "123456782"
    assert normalize_national_id("123-456-782") == "123456782"


def test_validate_accepts_valid_id() -> None:
    assert validate_national_id("123456782") == "123456782"


def test_validate_rejects_bad_checksum() -> None:
    with pytest.raises(ValueError, match="ספרת ביקורת"):
        validate_national_id("123456789")


def test_validate_rejects_empty() -> None:
    with pytest.raises(ValueError, match="יש להזין"):
        validate_national_id("")
