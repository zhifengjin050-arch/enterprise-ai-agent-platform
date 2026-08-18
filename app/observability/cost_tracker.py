"""LLM Usage Tracker — records per-call LLM usage to llm_usage_records.

Coexists with app/llm/cost/tracker.py (legacy); writes to the new
llm_usage_records table with richer attribution (tenant, user, agent, task).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.cost.tracker import _estimate_cost
from app.observability.models import LLMUsageRecord
from app.tenant.context import get_tenant_id, get_user_id


class LLMUsageTracker:
    """Record LLM usage to llm_usage_records with tenant/user/agent attribution."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        request_type: str = "other",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMUsageRecord:
        total = prompt_tokens + completion_tokens
        cost = _estimate_cost(model, prompt_tokens, completion_tokens)
        tid = tenant_id or get_tenant_id() or ""
        uid = user_id or get_user_id() or ""

        record = LLMUsageRecord(
            tenant_id=tid,
            user_id=uid,
            agent_id=agent_id or "",
            task_id=task_id or "",
            provider=provider,
            model=model,
            request_type=request_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost=cost,
        )
        self._session.add(record)
        await self._session.flush()

        # Also update legacy cost record if needed for backward compat
        try:
            from app.llm.cost.repository import CostRepository
            repo = CostRepository(self._session)
            await repo.create_record(
                provider=provider,
                model=model,
                request_type=request_type,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
                estimated_cost=cost,
            )
        except Exception:
            pass

        return record

    async def query(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> list[LLMUsageRecord]:
        from sqlalchemy import select

        stmt = select(LLMUsageRecord).order_by(LLMUsageRecord.created_at.desc())
        if tenant_id:
            stmt = stmt.where(LLMUsageRecord.tenant_id == tenant_id)
        if user_id:
            stmt = stmt.where(LLMUsageRecord.user_id == user_id)
        if agent_id:
            stmt = stmt.where(LLMUsageRecord.agent_id == agent_id)
        if since:
            stmt = stmt.where(LLMUsageRecord.created_at >= since)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def summary(self, *, tenant_id: str) -> Dict[str, Any]:
        """Return aggregated cost/token summary for a tenant."""
        from sqlalchemy import func, select

        stmt = select(
            func.count(LLMUsageRecord.id).label("total_calls"),
            func.sum(LLMUsageRecord.total_tokens).label("total_tokens"),
            func.sum(LLMUsageRecord.estimated_cost).label("total_cost"),
            func.sum(LLMUsageRecord.prompt_tokens).label("prompt_tokens"),
            func.sum(LLMUsageRecord.completion_tokens).label("completion_tokens"),
        ).where(LLMUsageRecord.tenant_id == tenant_id)
        row = (await self._session.execute(stmt)).one()
        return {
            "tenant_id": tenant_id,
            "total_calls": row.total_calls or 0,
            "total_tokens": int(row.total_tokens or 0),
            "total_cost": round(float(row.total_cost or 0.0), 6),
            "prompt_tokens": int(row.prompt_tokens or 0),
            "completion_tokens": int(row.completion_tokens or 0),
        }
