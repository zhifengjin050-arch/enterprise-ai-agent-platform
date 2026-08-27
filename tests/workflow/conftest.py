"""Pytest fixtures for workflow engine tests."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import app

_test_engine = None


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create an in-memory SQLite engine for workflow tests."""
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
    """FastAPI test client bypassing permission checks.

    Overrides get_current_user with a fake admin user and get_db with a
    test session. Patches AuthService.has_permission to always return True.
    """
    from unittest.mock import patch

    import app.workflow_engine.engine as wf_engine_module
    from app.auth.dependencies import get_current_user, get_db
    from app.auth.service import AuthService

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

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

    with (
        patch.object(AuthService, "has_permission", return_value=True),
        patch.object(wf_engine_module, "get_session_factory", return_value=factory),
    ):
        wf_engine_module.workflow_engine._session_factory = factory
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    # Clean up overrides
    app.dependency_overrides.clear()


# ──────────────────────────────────────────────
# Sample workflow JSON DSL definitions
# ──────────────────────────────────────────────


@pytest.fixture
def sample_workflow_definition() -> Dict[str, Any]:
    """Minimal valid workflow definition."""
    return {
        "name": "test_workflow",
        "description": "A test workflow",
        "version": "1.0",
        "nodes": [
            {
                "type": "trigger",
                "name": "start",
                "config": {},
                "next": "analysis",
            },
            {
                "type": "agent",
                "name": "analysis",
                "config": {"agent_name": "test_agent", "task": "Analyze the input"},
                "next": "finish",
            },
            {
                "type": "end",
                "name": "finish",
                "config": {},
            },
        ],
    }


@pytest.fixture
def sample_workflow_with_approval() -> Dict[str, Any]:
    """Workflow with approval node."""
    return {
        "name": "approval_workflow",
        "nodes": [
            {"type": "trigger", "name": "start", "next": "analysis"},
            {
                "type": "agent",
                "name": "analysis",
                "config": {"agent_name": "test_agent"},
                "next": "review",
            },
            {
                "type": "approval",
                "name": "review",
                "config": {"approvers": ["admin"], "message": "Approve?"},
                "next": "finish",
            },
            {"type": "end", "name": "finish"},
        ],
    }


@pytest.fixture
def sample_workflow_with_condition() -> Dict[str, Any]:
    """Workflow with condition node."""
    return {
        "name": "conditional_workflow",
        "nodes": [
            {"type": "trigger", "name": "start", "next": "check_score"},
            {
                "type": "condition",
                "name": "check_score",
                "config": {
                    "expression": "score > 0.5",
                    "true_next": "process",
                    "false_next": "reject",
                },
                "next": ["process", "reject"],
            },
            {
                "type": "agent",
                "name": "process",
                "config": {"agent_name": "process_agent"},
                "next": "finish",
            },
            {"type": "end", "name": "reject"},
            {"type": "end", "name": "finish"},
        ],
    }


@pytest.fixture
def sample_workflow_with_tool() -> Dict[str, Any]:
    """Workflow with tool node."""
    return {
        "name": "tool_workflow",
        "nodes": [
            {"type": "trigger", "name": "start", "next": "restart_pod"},
            {
                "type": "tool",
                "name": "restart_pod",
                "config": {
                    "tool_name": "k8s_restart",
                    "params": {"namespace": "default", "pod": "web-1"},
                },
                "next": "finish",
            },
            {"type": "end", "name": "finish"},
        ],
    }


@pytest.fixture
def invalid_workflow_no_trigger() -> Dict[str, Any]:
    """Invalid workflow — missing trigger."""
    return {
        "name": "bad_workflow",
        "nodes": [
            {"type": "agent", "name": "analysis", "config": {"agent_name": "test"}},
            {"type": "end", "name": "finish"},
        ],
    }


@pytest.fixture
def invalid_workflow_no_end() -> Dict[str, Any]:
    """Invalid workflow — missing end."""
    return {
        "name": "bad_workflow",
        "nodes": [
            {"type": "trigger", "name": "start"},
            {"type": "agent", "name": "analysis", "config": {"agent_name": "test"}},
        ],
    }
