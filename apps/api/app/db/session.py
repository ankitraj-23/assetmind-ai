"""Lazy SQLAlchemy engine and session management.

This module deliberately avoids opening any database connection at import
time. The engine is created on first use, and a clear error is raised when
``DATABASE_URL`` is required but missing. While the API runs in the default
JSON persistence mode, nothing here is touched.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database operation is attempted without DATABASE_URL."""


def get_database_url() -> str:
    """Return the configured database URL or raise a clear error.

    The URL is never read at import time; only explicit DB operations
    (sessions, migrations) call this helper.
    """

    if not settings.database_url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not set. A database connection string is required "
            "for database operations (e.g. running Alembic migrations or using "
            "the postgres persistence backend). Set DATABASE_URL in the "
            "environment or in apps/api/.env."
        )
    return settings.database_url


def get_engine() -> Engine:
    """Create (once) and return the SQLAlchemy engine.

    The engine is configured with ``pool_pre_ping`` so stale connections are
    recycled transparently. No connection is opened until the engine is first
    used to execute a statement.
    """

    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Create (once) and return the session factory bound to the engine."""

    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI-style dependency yielding a database session.

    Not wired into any route yet; provided for use once the postgres
    persistence backend is enabled.
    """

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
