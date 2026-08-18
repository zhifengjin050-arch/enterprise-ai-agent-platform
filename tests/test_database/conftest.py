"""Shared fixtures for database tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import app as fastapi_app

# Import models for metadata
import app.auth.models  # noqa: F401
import app.incident.models  # noqa: F401
import app.knowledge.models  # noqa: F401
import app.llm.cost.models  # noqa: F401
import app.sop.models  # noqa: F401
import app.connector.models  # noqa: F401
import app.task.models  # noqa: F401


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite async engine for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    reset_engine()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    """Yield an AsyncSession bound to the test engine."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def api_client(db_engine):
    """FastAPI test client with DB dependency overridden."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    fastapi_app.dependency_overrides.clear()
