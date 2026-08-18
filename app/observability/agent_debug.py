"""Agent Execution Debug Trace — persists step-level trace for debugging.

Augments Phase 6 AgentTrace with DB-persisted step records.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.models import AgentExecutionTrace
from app.tenant.context import get_tenant_id


class AgentDebugRecorder:
    """Record agent execution steps to agent_execution_traces table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_step(
        self,
        *,
        task_id: str,
        step: int,
        component: str,
        input: Optional[Dict[str, Any]] = None,
        output: Optional[Dict[str, Any]] = None,
        latency_ms: int = 0,
        success: bool = True,
        error: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> AgentExecutionTrace:
        trace = AgentExecutionTrace(
            task_id=task_id,
            tenant_id=tenant_id or get_tenant_id(),
            step=step,
            component=component,
            input_json=input or {},
            output_json=output or {},
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        self._session.add(trace)
        await self._session.flush()
        return trace

    async def get_traces(
        self,
        task_id: str,
        *,
        limit: int = 50,
    ) -> list[AgentExecutionTrace]:
        from sqlalchemy import select

        stmt = (
            select(AgentExecutionTrace)
            .where(AgentExecutionTrace.task_id == task_id)
            .order_by(AgentExecutionTrace.step.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def persist_agent_trace(
        self,
        session: AsyncSession,
        trace: Any,
        *,
        task_id: str,
    ) -> None:
        """Persist AgentTrace from Phase 6 into DB."""
        steps = []
        for i, t in enumerate(trace.tools or []):
            steps.append(
                AgentExecutionTrace(
                    task_id=task_id,
                    tenant_id=getattr(trace, "tenant_id", None) or get_tenant_id(),
                    step=i + 1,
                    component="tool",
                    input_json={},
                    output_json={},
                    latency_ms=t.get("latency_ms", 0),
                    success=t.get("success", True),
                    error=t.get("error"),
                )
            )
        for step in steps:
            session.add(step)
        await session.flush()
