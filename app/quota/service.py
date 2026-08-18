"""Quota service — plan assignment and consumption checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LLMQuotaException
from app.quota.models import DEFAULT_PLANS, QuotaPlan, QuotaPlanName


class QuotaService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def get_or_create(
        self,
        tenant_id: str,
        *,
        plan: str = QuotaPlanName.FREE.value,
    ) -> QuotaPlan:
        stmt = select(QuotaPlan).where(QuotaPlan.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            await self._maybe_reset(row)
            return row

        defaults = DEFAULT_PLANS.get(plan, DEFAULT_PLANS[QuotaPlanName.FREE.value])
        row = QuotaPlan(
            tenant_id=tenant_id,
            plan=plan,
            daily_tokens=int(defaults["daily_tokens"]),
            daily_agent_runs=int(defaults["daily_agent_runs"]),
            storage_mb=int(defaults["storage_mb"]),
            unlimited=bool(defaults["unlimited"]),
            usage_date=self._today(),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def _maybe_reset(self, row: QuotaPlan) -> None:
        today = self._today()
        if row.usage_date != today:
            row.used_tokens = 0
            row.used_agent_runs = 0
            row.usage_date = today
            await self._session.flush()

    async def status(self, tenant_id: str) -> Dict[str, Any]:
        row = await self.get_or_create(tenant_id)
        return row.to_dict()

    async def check_tokens(self, tenant_id: str, tokens: int = 1) -> None:
        row = await self.get_or_create(tenant_id)
        if row.unlimited:
            return
        if row.used_tokens + tokens > row.daily_tokens:
            raise LLMQuotaException(
                message="Daily LLM token quota exceeded",
                details={
                    "tenant_id": tenant_id,
                    "used": row.used_tokens,
                    "limit": row.daily_tokens,
                },
            )

    async def consume_tokens(self, tenant_id: str, tokens: int) -> None:
        await self.check_tokens(tenant_id, tokens)
        row = await self.get_or_create(tenant_id)
        if row.unlimited:
            return
        row.used_tokens += max(0, tokens)
        await self._session.flush()

    async def check_agent_run(self, tenant_id: str) -> None:
        row = await self.get_or_create(tenant_id)
        if row.unlimited:
            return
        if row.used_agent_runs + 1 > row.daily_agent_runs:
            raise LLMQuotaException(
                message="Daily agent run quota exceeded",
                details={
                    "tenant_id": tenant_id,
                    "used": row.used_agent_runs,
                    "limit": row.daily_agent_runs,
                },
            )

    async def consume_agent_run(self, tenant_id: str) -> None:
        await self.check_agent_run(tenant_id)
        row = await self.get_or_create(tenant_id)
        if row.unlimited:
            return
        row.used_agent_runs += 1
        await self._session.flush()

    async def set_plan(self, tenant_id: str, plan: str) -> QuotaPlan:
        defaults = DEFAULT_PLANS.get(plan)
        if defaults is None:
            raise ValueError(f"Unknown plan: {plan}")
        row = await self.get_or_create(tenant_id)
        row.plan = plan
        row.daily_tokens = int(defaults["daily_tokens"])
        row.daily_agent_runs = int(defaults["daily_agent_runs"])
        row.storage_mb = int(defaults["storage_mb"])
        row.unlimited = bool(defaults["unlimited"])
        await self._session.flush()
        return row
