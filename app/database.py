"""Database engine and session management (SQLAlchemy 2.0 style)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import database_path
from app.models.base import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the lazily-created singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        url = f"sqlite:///{database_path()}"
        _engine = create_engine(url, echo=False, future=True)
    return _engine


def init_db() -> None:
    """Create all tables and initialise the session factory.

    Importing the models module here guarantees that every mapped class is
    registered on ``Base.metadata`` before ``create_all`` runs.
    """
    global _SessionFactory
    import app.models  # noqa: F401  (ensures all models are imported)

    engine = get_engine()
    _pre_migrate(engine)
    Base.metadata.create_all(engine)
    _post_migrate(engine)
    _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _pre_migrate(engine: Engine) -> None:
    """Drop legacy tables whose schema changed, so they are recreated fresh.

    The ``tutor_subjects`` table used to store a single ``units`` value. It now
    stores per-grade qualifications (grade + units range), so an old-format
    table is dropped and rebuilt by ``create_all``. Tutor qualifications must be
    re-entered, which is expected since grade is now a required dimension.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "tutor_subjects" in tables:
        columns = {c["name"] for c in inspector.get_columns("tutor_subjects")}
        if "units_min" not in columns:
            with engine.begin() as conn:
                conn.exec_driver_sql("DROP TABLE tutor_subjects")


def _post_migrate(engine: Engine) -> None:
    """Add columns that were introduced after a table was first created.

    SQLite's ``create_all`` only creates missing tables, never alters existing
    ones, so newly-added columns are applied here with ``ALTER TABLE``.
    """
    inspector = inspect(engine)
    if "subjects" in set(inspector.get_table_names()):
        columns = {c["name"] for c in inspector.get_columns("subjects")}
        if "weekly_hours" not in columns:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE subjects "
                    "ADD COLUMN weekly_hours INTEGER NOT NULL DEFAULT 1"
                )


def get_session() -> Session:
    """Return a new ORM session. Caller is responsible for closing it."""
    if _SessionFactory is None:
        init_db()
    assert _SessionFactory is not None
    return _SessionFactory()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
