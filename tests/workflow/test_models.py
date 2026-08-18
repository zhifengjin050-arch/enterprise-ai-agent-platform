"""Tests for Workflow ORM models — Phase 9."""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.workflow_engine.models import (
    ApprovalStatus,
    NodeType,
    TriggerType,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowNode,
    WorkflowExecution,
    WorkflowStatus,
)


class TestWorkflowDefinitionModel:
    async def test_create(self, db_session: AsyncSession) -> None:
        wf = WorkflowDefinition(
            name="test_wf",
            definition={"name": "test_wf", "nodes": []},
        )
        db_session.add(wf)
        await db_session.commit()

        result = await db_session.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.name == "test_wf")
        )
        loaded = result.scalar_one()
        assert loaded.name == "test_wf"
        assert loaded.status == WorkflowStatus.CREATED

    async def test_repr(self) -> None:
        wf = WorkflowDefinition(name="test", definition={})
        assert "test" in repr(wf)

    async def test_default_status(self, db_session: AsyncSession) -> None:
        wf = WorkflowDefinition(name="test", definition={})
        db_session.add(wf)
        await db_session.flush()
        assert wf.status == WorkflowStatus.CREATED

    async def test_tenant_id(self) -> None:
        wf = WorkflowDefinition(name="test", definition={}, tenant_id="tenant-1")
        assert wf.tenant_id == "tenant-1"


class TestWorkflowNodeModel:
    async def test_create(self, db_session: AsyncSession) -> None:
        wf = WorkflowDefinition(name="test", definition={})
        db_session.add(wf)
        await db_session.flush()

        node = WorkflowNode(
            workflow_id=wf.id,
            node_type=NodeType.AGENT,
            node_name="analysis",
            config={"agent_name": "test"},
        )
        db_session.add(node)
        await db_session.commit()

        result = await db_session.execute(
            select(WorkflowNode).where(WorkflowNode.node_name == "analysis")
        )
        loaded = result.scalar_one()
        assert loaded.node_type == NodeType.AGENT
        assert loaded.config["agent_name"] == "test"

    async def test_unique_constraint(self, db_session: AsyncSession) -> None:
        wf = WorkflowDefinition(name="test", definition={})
        db_session.add(wf)
        await db_session.flush()

        db_session.add(WorkflowNode(workflow_id=wf.id, node_type=NodeType.TRIGGER, node_name="start"))
        await db_session.flush()

        with pytest.raises(Exception):  # IntegrityError
            db_session.add(WorkflowNode(workflow_id=wf.id, node_type=NodeType.END, node_name="start"))
            await db_session.flush()

    async def test_repr(self) -> None:
        node = WorkflowNode(workflow_id="x", node_type=NodeType.END, node_name="end")
        assert "end" in repr(node)


class TestWorkflowExecutionModel:
    async def test_create(self, db_session: AsyncSession) -> None:
        wf = WorkflowDefinition(name="test", definition={})
        db_session.add(wf)
        await db_session.flush()

        run = WorkflowExecution(
            workflow_id=wf.id,
            workflow_name="test",
            status=WorkflowStatus.RUNNING,
            context={"payload": {"input": "data"}},
        )
        db_session.add(run)
        await db_session.commit()

        result = await db_session.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_name == "test")
        )
        loaded = result.scalar_one()
        assert loaded.status == WorkflowStatus.RUNNING
        assert loaded.context["payload"]["input"] == "data"

    async def test_default_status(self, db_session: AsyncSession) -> None:
        run = WorkflowExecution(workflow_id="x")
        db_session.add(run)
        await db_session.flush()
        assert run.status == WorkflowStatus.CREATED

    async def test_repr(self) -> None:
        run = WorkflowExecution(workflow_id="x")
        assert "CREATED" in repr(run) or "WorkflowExecution" in repr(run)

    async def test_tenant_isolation(self) -> None:
        run = WorkflowExecution(workflow_id="x", tenant_id="t1")
        assert run.tenant_id == "t1"


class TestWorkflowEventModel:
    async def test_create(self, db_session: AsyncSession) -> None:
        wf = WorkflowDefinition(name="test", definition={})
        db_session.add(wf)
        await db_session.flush()

        run = WorkflowExecution(workflow_id=wf.id)
        db_session.add(run)
        await db_session.flush()

        event = WorkflowEvent(
            workflow_id=wf.id,
            run_id=run.id,
            node_name="start",
            event_type="node_start",
            event_data={"key": "value"},
        )
        db_session.add(event)
        await db_session.commit()

        result = await db_session.execute(
            select(WorkflowEvent).where(WorkflowEvent.event_type == "node_start")
        )
        loaded = result.scalar_one()
        assert loaded.node_name == "start"
        assert loaded.event_data["key"] == "value"

    async def test_repr(self) -> None:
        event = WorkflowEvent(workflow_id="x", event_type="test")
        assert "test" in repr(event)

    async def test_default_severity(self, db_session: AsyncSession) -> None:
        event = WorkflowEvent(workflow_id="x", event_type="test")
        db_session.add(event)
        await db_session.flush()
        assert event.severity == "info"