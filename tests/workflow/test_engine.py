"""Tests for WorkflowEngine — Phase 9."""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.workflow_engine.engine import WorkflowEngine
from app.workflow_engine.models import WorkflowStatus
from app.workflow_engine.parser import WorkflowValidationError


async def _shutdown_engine(eng: WorkflowEngine) -> None:
    """Cancel leftover background runs before the test DB engine is disposed."""
    pending = sum(1 for task in eng._active_runs.values() if task and not task.done())
    # #region agent log
    try:
        import json as _json
        import time as _time

        open(
            r"d:\代码项目\AI Agent项目\项目3：企业级 DevOps RAG 知识库 Agent\debug-f42d54.log",
            "a",
            encoding="utf-8",
        ).write(
            _json.dumps(
                {
                    "sessionId": "f42d54",
                    "runId": "post-fix",
                    "hypothesisId": "C",
                    "location": "tests/workflow/test_engine.py:_shutdown_engine",
                    "message": "fixture shutdown",
                    "data": {
                        "pending": pending,
                        "tracked": len(eng._active_runs),
                        "via": "engine.shutdown",
                    },
                    "timestamp": int(_time.time() * 1000),
                }
            )
            + "\n"
        )
    except Exception:
        pass
    # #endregion
    await eng.shutdown()


class TestWorkflowEngineDefinitionCRUD:
    """Tests for workflow definition lifecycle."""

    @pytest.fixture
    async def engine(self, db_engine) -> WorkflowEngine:
        test_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        eng = WorkflowEngine(session_factory=test_factory)
        yield eng
        await _shutdown_engine(eng)

    async def test_create_workflow(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        result = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        assert result["name"] == "test_workflow"
        assert result["status"] == "CREATED"
        assert result["tenant_id"] == "t1"
        assert result["node_count"] == 3

    async def test_create_workflow_invalid(self, engine: WorkflowEngine) -> None:
        with pytest.raises(WorkflowValidationError):
            await engine.create_workflow({"name": "bad"})

    async def test_get_workflow(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        fetched = await engine.get_workflow(created["id"], tenant_id="t1")
        assert fetched is not None
        assert fetched["id"] == created["id"]

    async def test_get_workflow_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.get_workflow("nonexistent")
        assert result is None

    async def test_get_workflow_wrong_tenant(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        result = await engine.get_workflow(created["id"], tenant_id="t2")
        assert result is None

    async def test_get_workflows_list(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        workflows = await engine.get_workflows(tenant_id="t1")
        assert len(workflows) == 2

    async def test_get_workflows_empty(self, engine: WorkflowEngine) -> None:
        workflows = await engine.get_workflows(tenant_id="t1")
        assert len(workflows) == 0

    async def test_get_workflows_status_filter(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        workflows = await engine.get_workflows(tenant_id="t1", status=WorkflowStatus.CREATED)
        assert len(workflows) == 1
        workflows = await engine.get_workflows(tenant_id="t1", status=WorkflowStatus.COMPLETED)
        assert len(workflows) == 0

    async def test_update_workflow(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        updated = await engine.update_workflow(created["id"], {"name": "new_name"}, tenant_id="t1")
        assert updated is not None
        assert updated["name"] == "new_name"

    async def test_update_workflow_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.update_workflow("nonexistent", {"name": "new"})
        assert result is None

    async def test_delete_workflow(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        deleted = await engine.delete_workflow(created["id"], tenant_id="t1")
        assert deleted is True
        fetched = await engine.get_workflow(created["id"], tenant_id="t1")
        assert fetched is None

    async def test_delete_workflow_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.delete_workflow("nonexistent")
        assert result is False

    async def test_get_workflow_returns_tenant(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="tenant-42")
        assert created["tenant_id"] == "tenant-42"

    async def test_get_workflow_includes_node_count(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition)
        assert created["node_count"] == 3


class TestWorkflowEngineExecution:
    """Tests for workflow execution lifecycle."""

    @pytest.fixture
    async def engine(self, db_engine) -> WorkflowEngine:
        test_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        eng = WorkflowEngine(session_factory=test_factory)
        yield eng
        await _shutdown_engine(eng)

    async def test_execute_workflow(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        result = await engine.execute_workflow(
            created["id"],
            trigger_type="api",
            trigger_payload={"input": "test"},
            tenant_id="t1",
        )
        assert result["status"] == "RUNNING"
        assert result["workflow_id"] == created["id"]

    async def test_execute_workflow_not_found(self, engine: WorkflowEngine) -> None:
        with pytest.raises(ValueError, match="not found"):
            await engine.execute_workflow("nonexistent")

    async def test_execute_workflow_invalid_trigger(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        # Webhook with no secret always passes; try schedule with unknown config

        with pytest.raises(ValueError):
            await engine.execute_workflow(
                created["id"],
                trigger_type="unknown_trigger",
                trigger_payload={},
                tenant_id="t1",
            )

    async def test_get_run(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        fetched = await engine.get_run(run["id"], tenant_id="t1")
        assert fetched is not None
        assert fetched["id"] == run["id"]

    async def test_get_run_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.get_run("nonexistent")
        assert result is None

    async def test_get_runs_for_workflow(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        await engine.execute_workflow(created["id"], tenant_id="t1")
        runs = await engine.get_runs(workflow_id=created["id"], tenant_id="t1")
        assert len(runs) == 1

    async def test_pause_workflow(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        # Use approval workflow which WAITS at the approval node
        await asyncio.sleep(0.2)
        paused = await engine.pause_workflow(run["id"], tenant_id="t1")
        assert paused is not None
        assert paused["status"] == "PAUSED"

    async def test_pause_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.pause_workflow("nonexistent")
        assert result is None

    async def test_resume_workflow(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        import asyncio

        await asyncio.sleep(0.2)
        await engine.pause_workflow(run["id"], tenant_id="t1")
        resumed = await engine.resume_workflow(run["id"], tenant_id="t1")
        assert resumed is not None
        assert resumed["status"] == "RUNNING"

    async def test_resume_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.resume_workflow("nonexistent")
        assert result is None

    async def test_cancel_workflow(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        import asyncio

        await asyncio.sleep(0.2)
        cancelled = await engine.cancel_workflow(run["id"], tenant_id="t1")
        assert cancelled is not None
        assert cancelled["status"] == "FAILED"
        assert cancelled["error"] == "Cancelled by user"

    async def test_cancel_not_found(self, engine: WorkflowEngine) -> None:
        result = await engine.cancel_workflow("nonexistent")
        assert result is None

    async def test_get_run_events(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        import asyncio

        await asyncio.sleep(0.5)
        events = await engine.get_run_events(run["id"], tenant_id="t1")
        # At minimum should have node_start and node_end events
        assert len(events) >= 2

    async def test_tenant_isolation_runs(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        await engine.execute_workflow(created["id"], tenant_id="t1")
        runs_t1 = await engine.get_runs(tenant_id="t1")
        runs_t2 = await engine.get_runs(tenant_id="t2")
        assert len(runs_t1) == 1
        assert len(runs_t2) == 0


class TestWorkflowEngineEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    async def engine(self, db_engine) -> WorkflowEngine:
        test_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        eng = WorkflowEngine(session_factory=test_factory)
        yield eng
        await _shutdown_engine(eng)

    async def test_create_with_approval_workflow(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        result = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        assert result["node_count"] == 4

    async def test_create_with_condition_workflow(
        self, engine: WorkflowEngine, sample_workflow_with_condition: Dict[str, Any]
    ) -> None:
        result = await engine.create_workflow(sample_workflow_with_condition, tenant_id="t1")
        assert result["node_count"] == 5

    async def test_create_with_tool_workflow(
        self, engine: WorkflowEngine, sample_workflow_with_tool: Dict[str, Any]
    ) -> None:
        result = await engine.create_workflow(sample_workflow_with_tool, tenant_id="t1")
        assert result["node_count"] == 3

    async def test_execute_twice_fails(
        self, engine: WorkflowEngine, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_definition, tenant_id="t1")
        await engine.execute_workflow(created["id"], tenant_id="t1")
        with pytest.raises(ValueError, match="already running"):
            await engine.execute_workflow(created["id"], tenant_id="t1")

    async def test_cancel_cancels_task(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        with patch.object(engine._approval_service, "create_approval") as mock_create:
            mock_create.return_value = {"id": "mock-approval-id", "status": "PENDING"}
            run = await engine.execute_workflow(created["id"], tenant_id="t1")
            import asyncio

            await asyncio.sleep(0.05)
            # Cancel on the run, should still be active
            await engine.cancel_workflow(run["id"], tenant_id="t1")
            await asyncio.sleep(0.1)
            assert run["id"] not in engine._active_runs

    async def test_pause_saves_state(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        import asyncio

        # Wait for workflow to reach WAITING state at approval node
        await asyncio.sleep(0.3)
        paused = await engine.pause_workflow(run["id"], tenant_id="t1")
        assert paused is not None
        assert paused["status"] == "PAUSED"
        assert run["id"] in engine._paused_runs

    async def test_resume_clears_paused(
        self, engine: WorkflowEngine, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = await engine.create_workflow(sample_workflow_with_approval, tenant_id="t1")
        run = await engine.execute_workflow(created["id"], tenant_id="t1")
        import asyncio

        await asyncio.sleep(0.3)
        await engine.pause_workflow(run["id"], tenant_id="t1")
        await engine.resume_workflow(run["id"], tenant_id="t1")
        await asyncio.sleep(0.1)
        assert run["id"] not in engine._paused_runs
