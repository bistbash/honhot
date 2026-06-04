"""Shared pytest fixtures: isolate the database in a temp file per test."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as db
import app.models  # noqa: F401  (registers all mapped classes)
from app.models.base import Base


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the application's session factory at a throwaway SQLite file."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setattr(db, "_SessionFactory", factory)
    yield
    engine.dispose()
