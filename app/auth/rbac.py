"""PermissionChecker — RBAC facade used by routes and Agent Runtime."""

from __future__ import annotations

from typing import Optional, Set, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService
from app.core.exceptions import PermissionDenied
from app.tenant.context import get_tenant_context


class PermissionChecker:
    """Check permissions for a user (or API-key principal).

    Usage::

        checker = PermissionChecker(session)
        await checker.require("agent.execute", user_id=...)
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        service: Optional[AuthService] = None,
    ) -> None:
        self._session = session
        self._service = service or AuthService()

    async def get_permissions(self, user_id: Union[str, None]) -> Set[str]:
        if not user_id:
            ctx = get_tenant_context()
            if ctx and ctx.auth_method == "api_key":
                # API keys inherit a broad read/execute set by default
                return {
                    "knowledge.read",
                    "connector.read",
                    "connector.sync",
                    "agent.read",
                    "agent.execute",
                }
            return set()
        return await self._service.get_user_permissions(self._session, user_id)

    async def has(
        self,
        permission_code: str,
        *,
        user_id: Optional[str] = None,
    ) -> bool:
        ctx = get_tenant_context()
        uid = user_id or (ctx.user_id if ctx else None)
        perms = await self.get_permissions(uid)
        if permission_code in perms:
            return True
        # admin.manage grants all
        if "admin.manage" in perms:
            return True
        return False

    async def require(
        self,
        permission_code: str,
        *,
        user_id: Optional[str] = None,
    ) -> None:
        ok = await self.has(permission_code, user_id=user_id)
        if not ok:
            raise PermissionDenied(
                message=f"Missing required permission: {permission_code}",
                details={"permission": permission_code},
            )
