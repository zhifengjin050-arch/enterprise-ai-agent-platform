"""Shared fixtures for connector tests."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import app as fastapi_app

# Import models so Base.metadata is complete
import app.auth.models  # noqa: F401
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


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample connector config dict for testing."""
    return {
        "app_id": "test_app_id",
        "app_secret": "test_app_secret",
    }


@pytest.fixture
def connector_document_data() -> Dict[str, Any]:
    """Sample ConnectorDocument dict."""
    return {
        "id": "doc_001",
        "title": "Test Document",
        "content": "# Test\n\nContent here.",
        "url": "https://example.com/docs/1",
        "updated_at": "2026-08-17T12:00:00+00:00",
        "metadata": {"source": "test", "tags": ["test"]},
    }


@pytest.fixture
def auth_header() -> Dict[str, str]:
    """Return a dummy Authorization header for API tests.

    Most API tests use require_permission which expects a valid JWT.
    We'll override the dependency in individual tests to simplify.
    """
    return {"Authorization": "Bearer dummy_token"}