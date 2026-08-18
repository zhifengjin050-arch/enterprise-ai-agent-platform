"""Dashboard API — /api/metrics/* endpoints for observability.

All endpoints require admin.monitor permission.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_session
from app.observability.models import AgentExecutionTrace, LLMUsageRecord, SystemEvent
from app.tenant.context import get_tenant_id

router = APIRouter(prefix="/api/metrics", tags=["monitor", "metrics"])


async def _check_db(session: AsyncSession) -> bool:
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/overview")
async def metrics_overview(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("admin.monitor")),
) -> dict:
    """System health overview with aggregate metrics."""
    db_ok = await _check_db(session)
    tenant_id = get_tenant_id()

    # Quick counts (last 24h)
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    since_str = since_24h.isoformat()

    async def count_llm() -> int:
        stmt = select(func.count(LLMUsageRecord.id))
        if tenant_id:
            stmt = stmt.where(LLMUsageRecord.tenant_id == tenant_id)
        stmt = stmt.where(LLMUsageRecord.created_at >= since_24h)
        return (await session.execute(stmt)).scalar() or 0

    async def count_agent() -> int:
        stmt = select(func.count(AgentExecutionTrace.id))
        if tenant_id:
            stmt = stmt.where(AgentExecutionTrace.tenant_id == tenant_id)
        stmt = stmt.where(AgentExecutionTrace.created_at >= since_24h)
        return (await session.execute(stmt)).scalar() or 0

    async def count_errors() -> int:
        stmt = select(func.count(SystemEvent.id)).where(
            SystemEvent.event_type == "error"
        )
        if tenant_id:
            stmt = stmt.where(SystemEvent.tenant_id == tenant_id)
        stmt = stmt.where(SystemEvent.created_at >= since_24h)
        return (await session.execute(stmt)).scalar() or 0

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "period_hours": 24,
        "llm_calls": await count_llm(),
        "agent_executions": await count_agent(),
        "errors_24h": await count_errors(),
        "tenant_id": tenant_id,
    }


@router.get("/agents")
async def metrics_agents(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("admin.monitor")),
) -> dict:
    """Agent execution statistics."""
    tenant_id = get_tenant_id()
    base = select(AgentExecutionTrace)
    if tenant_id:
        base = base.where(AgentExecutionTrace.tenant_id == tenant_id)

    # Component breakdown
    counts_result = await session.execute(
        select(
            AgentExecutionTrace.component,
            func.count(AgentExecutionTrace.id).label("count"),
        )
        .select_from(AgentExecutionTrace)
        .where(AgentExecutionTrace.tenant_id == tenant_id if tenant_id else True)
        .group_by(AgentExecutionTrace.component)
    )
    components = {row.component: row.count for row in counts_result.all()}

    # Success rate
    total = (
        await session.execute(
            select(func.count(AgentExecutionTrace.id)).where(
                AgentExecutionTrace.tenant_id == tenant_id if tenant_id else True
            )
        )
    ).scalar() or 0
    failed = (
        await session.execute(
            select(func.count(AgentExecutionTrace.id)).where(
                AgentExecutionTrace.success == False,
                AgentExecutionTrace.tenant_id == tenant_id if tenant_id else True,
            )
        )
    ).scalar() or 0

    return {
        "total_executions": total,
        "failed": failed,
        "success_rate": round((1 - failed / max(total, 1)) * 100, 2),
        "components": components,
        "tenant_id": tenant_id,
    }


@router.get("/llm")
async def metrics_llm(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("admin.monitor")),
) -> dict:
    """LLM consumption statistics."""
    tenant_id = get_tenant_id()
    base = select(LLMUsageRecord)
    if tenant_id:
        base = base.where(LLMUsageRecord.tenant_id == tenant_id)

    # Aggregated
    agg = (await session.execute(
        select(
            func.count(LLMUsageRecord.id).label("calls"),
            func.sum(LLMUsageRecord.total_tokens).label("tokens"),
            func.sum(LLMUsageRecord.estimated_cost).label("cost"),
            func.sum(LLMUsageRecord.prompt_tokens).label("prompt"),
            func.sum(LLMUsageRecord.completion_tokens).label("completion"),
        ).where(LLMUsageRecord.tenant_id == tenant_id if tenant_id else True)
    )).one()

    # Per model
    per_model = (await session.execute(
        select(
            LLMUsageRecord.model,
            func.count(LLMUsageRecord.id).label("calls"),
            func.sum(LLMUsageRecord.total_tokens).label("tokens"),
            func.sum(LLMUsageRecord.estimated_cost).label("cost"),
        )
        .group_by(LLMUsageRecord.model)
    )).all()

    return {
        "total_calls": agg.calls or 0,
        "total_tokens": int(agg.tokens or 0),
        "total_cost": round(float(agg.cost or 0), 6),
        "prompt_tokens": int(agg.prompt or 0),
        "completion_tokens": int(agg.completion or 0),
        "per_model": [
            {"model": r.model, "calls": r.calls, "tokens": int(r.tokens or 0), "cost": round(float(r.cost or 0), 6)}
            for r in per_model
        ],
        "tenant_id": tenant_id,
    }


@router.get("/sync")
async def metrics_sync(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("admin.monitor")),
) -> dict:
    """Sync job statistics (from sync_engine events)."""
    try:
        from app.sync_engine.models import SyncEventRecord

        base = select(SyncEventRecord)
        total = (await session.execute(
            select(func.count(SyncEventRecord.id))
        )).scalar() or 0
        failed = (await session.execute(
            select(func.count(SyncEventRecord.id)).where(SyncEventRecord.event_type == "error")
        )).scalar() or 0

        return {
            "total_syncs": total,
            "failed": failed,
            "success_rate": round((1 - failed / max(total, 1)) * 100, 2),
        }
    except Exception:
        return {
            "total_syncs": 0,
            "failed": 0,
            "success_rate": 100.0,
            "note": "sync_engine table not yet available",
        }


@router.get("/errors")
async def metrics_errors(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("admin.monitor")),
) -> dict:
    """Error statistics from system_events."""
    tenant_id = get_tenant_id()
    base = select(SystemEvent).where(SystemEvent.event_type == "error")
    if tenant_id:
        base = base.where(SystemEvent.tenant_id == tenant_id)

    total = (await session.execute(
        select(func.count(SystemEvent.id)).where(
            SystemEvent.tenant_id == tenant_id if tenant_id else True,
        )
    )).scalar() or 0

    per_component = (await session.execute(
        select(
            SystemEvent.component,
            func.count(SystemEvent.id).label("count"),
        )
        .group_by(SystemEvent.component)
    )).all()

    return {
        "total_errors": total,
        "per_component": {r.component: r.count for r in per_component},
        "tenant_id": tenant_id,
    }
