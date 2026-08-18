"""
Async database session management.

Provides AsyncEngine, async session factory, and FastAPI dependency.
Supports SQLite (development) and PostgreSQL (production).
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _build_engine_kwargs(database_url: str, echo: bool) -> dict:
    """Build create_async_engine kwargs based on dialect.

    Args:
        database_url: SQLAlchemy database URL.
        echo: Whether to echo SQL statements.

    Returns:
        Keyword arguments for create_async_engine.
    """
    kwargs: dict = {
        "echo": echo,
        "future": True,
    }
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL connection pool settings
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 1800
    return kwargs


def create_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine from settings.

    Args:
        database_url: Optional override URL.

    Returns:
        AsyncEngine instance.
    """
    settings = get_settings()
    url = database_url or settings.database_url
    return create_async_engine(url, **_build_engine_kwargs(url, settings.debug))


def create_session_factory(
    engine: Optional[AsyncEngine] = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: Optional engine; creates one if omitted.

    Returns:
        async_sessionmaker bound to the engine.
    """
    if engine is None:
        engine = create_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_engine() -> AsyncEngine:
    """Return the process-wide AsyncEngine singleton."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession.

    Commits on success, rolls back on error, then closes the session.

    Yields:
        AsyncSession instance.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Backward-compatible alias used by earlier modules
get_session = get_db


async def init_db() -> None:
    """Create all tables from Base.metadata (development helper).

    Prefer Alembic migrations in production.
    """
    # Import models so metadata is populated
    import app.incident.models  # noqa: F401
    import app.knowledge.models  # noqa: F401
    import app.sop.models  # noqa: F401
    from app.db.base import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def reset_engine() -> None:
    """Reset global engine/session factory (used in tests)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
