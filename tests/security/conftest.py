"""Shared fixtures for security / multi-tenant tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agent_runtime.models  # noqa: F401
import app.api_key.models  # noqa: F401
import app.audit.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.auth.organization  # noqa: F401
import app.quota.models  # noqa: F401
from app.auth.dependencies import get_current_user
from app.auth.service import AuthService
from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import app as fastapi_app


@pytest_asyncio.fixture
async def db_engine():
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    reset_engine()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def tenant_user(db_session):
    from app.auth.models import Tenant
    from app.auth.repository import UserRepository

    tenant = Tenant(name=f"t-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    svc = AuthService()
    hashed = svc._hash_password("secret123")
    repo = UserRepository(db_session)
    user = await repo.create_user(
        username=f"u-{uuid.uuid4().hex[:8]}",
        hashed_password=hashed,
        email="u@example.com",
        tenant_id=str(tenant.id),
    )
    await db_session.flush()
    return {"tenant": tenant, "user": user, "password": "secret123"}


@pytest_asyncio.fixture
async def api_client(db_engine):
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


@pytest_asyncio.fixture
async def auth_client(db_engine, tenant_user):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    user = tenant_user["user"]
    tenant = tenant_user["tenant"]

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _fake_user():
        return {
            "id": str(user.id),
            "username": user.username,
            "tenant_id": str(tenant.id),
            "roles": ["admin"],
            "is_active": True,
        }

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_current_user] = _fake_user

    with patch.object(AuthService, "has_permission", new_callable=AsyncMock, return_value=True):
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, tenant_user

    fastapi_app.dependency_overrides.clear()
