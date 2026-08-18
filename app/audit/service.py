"""Audit event recorder."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.tenant.context import get_tenant_context
from app.tenant.isolation import apply_tenant_filter


class AuditEvent:
    """Facade for writing and querying audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        action: str,
        *,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        ctx = get_tenant_context()
        log = AuditLog(
            action=action,
            resource=resource,
            resource_id=resource_id,
            tenant_id=tenant_id or (ctx.tenant_id if ctx else None),
            user_id=user_id or (ctx.user_id if ctx else None),
            ip=ip,
            user_agent=user_agent,
            details_json=details or {},
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_logs(
        self,
        *,
        tenant_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        stmt = apply_tenant_filter(stmt, AuditLog.tenant_id, tenant_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
