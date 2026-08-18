"""Pytest fixtures for observability tests."""
from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

_test_engine = None


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create an in-memory SQLite engine for observability tests."""
    global _test_engine
    _test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _test_engine
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh session per test with rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    yield session
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client (no auth required)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_api_client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client bypassing permission checks for monitor endpoints.

    Overrides get_current_user with a fake admin user and get_db with a
    test session. Patches AuthService.has_permission to always return True.
    """
    from unittest.mock import patch
    from app.auth.dependencies import get_current_user
    from app.auth.service import AuthService

    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fake_user = {
        "id": "00000000-0000-0000-0000-000000000001",
        "username": "admin",
        "email": "admin@test.com",
        "is_active": True,
        "tenant_id": "00000000-0000-0000-0000-0000000000aa",
        "roles": ["admin"],
    }

    async def _override_get_current_user():
        return fake_user

    # Set overrides
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with patch.object(AuthService, "has_permission", return_value=True):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    # Clean up overrides
    app.dependency_overrides.clear()