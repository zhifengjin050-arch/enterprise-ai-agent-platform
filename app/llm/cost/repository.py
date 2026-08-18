"""Cost repository for LLMCostRecord persistence.

All cost-related DB operations go through this repository.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.cost.models import LLMCostRecord


class CostRepository:
    """Async repository for LLM cost records.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_record(
        self,
        *,
        provider: str = "unknown",
        model: str = "unknown",
        request_type: str = "other",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> LLMCostRecord:
        """Create a new cost record.

        Args:
            provider: LLM provider name.
            model: Model name.
            request_type: Request category.
            prompt_tokens: Input tokens.
            completion_tokens: Output tokens.
            total_tokens: Total tokens.
            estimated_cost: Estimated USD cost.

        Returns:
            Persisted LLMCostRecord.
        """
        record = LLMCostRecord(
            provider=provider,
            model=model,
            request_type=request_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_today_stats(self) -> Dict[str, Any]:
        """Get today's cost statistics.

        Returns:
            Dict with total_tokens, total_cost, request_count.
        """
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = select(LLMCostRecord).where(
            LLMCostRecord.created_at >= today_start
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        return {
            "total_tokens": sum(r.total_tokens for r in records),
            "total_cost": round(sum(r.estimated_cost for r in records), 6),
            "request_count": len(records),
        }

    async def get_month_stats(self) -> Dict[str, Any]:
        """Get this month's cost statistics.

        Returns:
            Dict with total_tokens, total_cost, request_count.
        """
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        stmt = select(LLMCostRecord).where(
            LLMCostRecord.created_at >= month_start
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        return {
            "total_tokens": sum(r.total_tokens for r in records),
            "total_cost": round(sum(r.estimated_cost for r in records), 6),
            "request_count": len(records),
        }

    async def get_stats_by_model(self) -> List[Dict[str, Any]]:
        """Get cost statistics grouped by model.

        Returns:
            List of dicts per model.
        """
        stmt = select(LLMCostRecord)
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        model_stats: Dict[str, Dict] = {}
        for r in records:
            if r.model not in model_stats:
                model_stats[r.model] = {
                    "model": r.model,
                    "request_count": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            model_stats[r.model]["request_count"] += 1
            model_stats[r.model]["total_tokens"] += r.total_tokens
            model_stats[r.model]["total_cost"] += r.estimated_cost

        for stat in model_stats.values():
            stat["total_cost"] = round(stat["total_cost"], 6)

        return list(model_stats.values())
