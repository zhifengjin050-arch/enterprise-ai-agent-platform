"""Admin API endpoints.

Provides LLM cost statistics and system admin features.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.llm.cost.repository import CostRepository

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/llm/cost")
async def get_llm_cost_stats(
    session: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get LLM cost statistics.

    Requires the 'admin.llm' permission.

    Returns:
        Dict with today, month, and per-model stats.
    """
    # Check permission manually
    from app.auth.service import AuthService

    if current_user is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    service = AuthService()
    has_perm = await service.has_permission(
        session, current_user["id"], "admin.llm"
    )
    if not has_perm:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: admin.llm",
        )

    repo = CostRepository(session)
    today = await repo.get_today_stats()
    month = await repo.get_month_stats()
    by_model = await repo.get_stats_by_model()

    return {
        "today": today,
        "month": month,
        "by_model": by_model,
    }
