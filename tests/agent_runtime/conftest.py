"""Shared fixtures for agent_runtime tests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agent_runtime.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.connector.models  # noqa: F401
import app.prompt.models  # noqa: F401
import app.sync_engine.models  # noqa: F401
import app.task.models  # noqa: F401
from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult
from app.agent_runtime.tools.registry import ToolRegistry
from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import app as fastapi_app


class StubTool(BaseTool):
    """Deterministic tool for unit tests."""

    name = "stub_tool"
    description = "A stub tool for tests"
    permissions = ["knowledge.read"]

    def __init__(
        self,
        *,
        name: str = "stub_tool",
        data: Any = None,
        fail: bool = False,
        permissions: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self._data = data if data is not None else [{"title": "Stub", "content": "ok"}]
        self._fail = fail
        if permissions is not None:
            self.permissions = permissions

    async def execute(self, input: Dict[str, Any], context: ToolContext) -> ToolResult:
        if self._fail:
            return ToolResult(success=False, error="stub failure")
        return ToolResult(success=True, data=self._data, metadata={"input": input})


class FakeLLM:
    """Fake LLM gateway for agent tests."""

    def __init__(self, answer: str = "测试答案") -> None:
        self._answer = answer
        self.calls = 0

    async def chat(self, message: str, system_prompt=None, temperature=0.3, **kwargs) -> str:
        self.calls += 1
        return self._answer

    def get_model_name(self) -> str:
        return "fake-model"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
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

    async def _allow():
        return None

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    # Bypass permission checks for happy-path tests via override of factory results
    # We override require_permission by patching each call site through a helper.
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_api_client(db_engine):
    """API client with permission checks bypassed."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from app.auth.dependencies import get_current_user
    from app.auth.service import AuthService

    async def _fake_user():
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "username": "tester",
            "tenant_id": "00000000-0000-0000-0000-0000000000aa",
            "roles": ["admin"],
            "is_active": True,
        }

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_current_user] = _fake_user

    with patch.object(AuthService, "has_permission", new_callable=AsyncMock, return_value=True):
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(StubTool(name="knowledge_search"))
    reg.register(StubTool(name="graph_query", data={"nodes": [], "edges": []}))
    reg.register(StubTool(name="document_query", data={"id": "d1", "title": "Doc"}))
    reg.register(StubTool(name="connector_sync", data={"job_id": "j1"}))
    return reg


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
