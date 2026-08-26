"""Tests for Agent Debug Trace (AgentExecutionTrace)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.observability.agent_debug import AgentDebugRecorder
from app.observability.models import AgentExecutionTrace


class TestAgentDebugRecorder:
    """AgentDebugRecorder integration tests."""

    @pytest.mark.asyncio
    async def test_record_step_creates_trace(self, db_session):
        recorder = AgentDebugRecorder(db_session)
        trace = await recorder.record_step(
            task_id="task-1",
            step=1,
            component="planner",
            input={"query": "test"},
            output={"plan": "step1"},
            latency_ms=100,
        )
        assert trace.id is not None
        assert trace.task_id == "task-1"
        assert trace.component == "planner"
        assert trace.latency_ms == 100

    @pytest.mark.asyncio
    async def test_record_step_persists(self, db_session):
        recorder = AgentDebugRecorder(db_session)
        await recorder.record_step(
            task_id="task-persist",
            step=1,
            component="tool",
            output={"result": "ok"},
        )
        result = await db_session.execute(
            select(AgentExecutionTrace).where(AgentExecutionTrace.task_id == "task-persist")
        )
        traces = list(result.scalars().all())
        assert len(traces) >= 1

    @pytest.mark.asyncio
    async def test_multi_step_trace(self, db_session):
        recorder = AgentDebugRecorder(db_session)
        steps = ["planner", "tool", "retriever", "llm", "final"]
        for i, comp in enumerate(steps, 1):
            await recorder.record_step(
                task_id="multi-step",
                step=i,
                component=comp,
                latency_ms=i * 50,
            )

        traces = await recorder.get_traces("multi-step")
        assert len(traces) == len(steps)
        for i, t in enumerate(traces):
            assert t.component == steps[i]

    @pytest.mark.asyncio
    async def test_record_step_with_error(self, db_session):
        recorder = AgentDebugRecorder(db_session)
        trace = await recorder.record_step(
            task_id="err-task",
            step=2,
            component="llm",
            success=False,
            error="LLM timeout",
            latency_ms=5000,
        )
        assert trace.success is False
        assert trace.error == "LLM timeout"

    @pytest.mark.asyncio
    async def test_get_traces_ordered(self, db_session):
        recorder = AgentDebugRecorder(db_session)
        for i in range(3, 0, -1):  # insert in reverse order
            await recorder.record_step(
                task_id="ordered",
                step=i,
                component=f"step-{i}",
            )
        traces = await recorder.get_traces("ordered")
        # Should be ordered by step asc
        steps = [t.step for t in traces]
        assert steps == sorted(steps)

    @pytest.mark.asyncio
    async def test_get_traces_empty(self, db_session):
        recorder = AgentDebugRecorder(db_session)
        traces = await recorder.get_traces("nonexistent")
        assert traces == []

    @pytest.mark.asyncio
    async def test_record_step_auto_tenant(self, db_session):
        from app.tenant.context import TenantContext, clear_tenant_context, set_tenant_context

        ctx = TenantContext(tenant_id="auto-t1")
        token = set_tenant_context(ctx)
        try:
            recorder = AgentDebugRecorder(db_session)
            trace = await recorder.record_step(
                task_id="auto-tenant",
                step=1,
                component="test",
            )
            assert trace.tenant_id == "auto-t1"
        finally:
            clear_tenant_context(token)


class TestAgentTraceModel:
    """AgentExecutionTrace model standalone."""

    def test_model_has_required_fields(self):
        t = AgentExecutionTrace()
        assert hasattr(t, "task_id")
        assert hasattr(t, "step")
        assert hasattr(t, "component")
        assert hasattr(t, "latency_ms")
        assert hasattr(t, "success")

    def test_to_dict_maps_json_fields(self):
        t = AgentExecutionTrace(
            task_id="t1",
            step=1,
            component="tool",
            input_json={"arg": "val"},
            output_json={"result": "ok"},
            latency_ms=200,
            success=True,
        )
        d = t.to_dict()
        assert d["input"] == {"arg": "val"}
        assert d["output"] == {"result": "ok"}

    def test_default_success(self):
        t = AgentExecutionTrace(success=True)
        assert t.success is True
