"""TenantMiddleware — parse identity and inject TenantContext."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.tenant.context import TenantContext, clear_tenant_context, set_tenant_context

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant/user from JWT or API key headers into TenantContext.

    Resolution order:
        1. Authorization: Bearer <jwt>
        2. X-API-Key / Authorization: ApiKey <key>
        3. X-Tenant-ID header (only when already authenticated via API key)
        4. Anonymous empty context

    Does not block unauthenticated requests — RBAC stays at route level.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        ctx = await self._resolve(request)
        token = set_tenant_context(ctx)
        request.state.tenant_id = ctx.tenant_id
        request.state.user_id = ctx.user_id
        request.state.organization_id = ctx.organization_id
        try:
            response = await call_next(request)
            if ctx.tenant_id:
                response.headers["X-Tenant-ID"] = ctx.tenant_id
            return response
        finally:
            clear_tenant_context(token)

    async def _resolve(self, request: Request) -> TenantContext:
        auth = request.headers.get("Authorization") or ""
        api_key = request.headers.get("X-API-Key") or ""

        # JWT Bearer
        if auth.lower().startswith("bearer "):
            raw = auth.split(" ", 1)[1].strip()
            ctx = self._from_jwt(raw)
            if ctx is not None:
                return ctx

        # API Key
        key_value = api_key.strip()
        if not key_value and auth.lower().startswith("apikey "):
            key_value = auth.split(" ", 1)[1].strip()
        if key_value:
            ctx = await self._from_api_key(key_value, request)
            if ctx is not None:
                return ctx

        # Anonymous — optional explicit tenant header is ignored for security
        return TenantContext()

    def _from_jwt(self, token: str) -> Optional[TenantContext]:
        try:
            from app.auth.jwt import decode_access_token

            payload = decode_access_token(token)
            if not payload or payload.get("type") == "refresh":
                return None
            return TenantContext(
                tenant_id=payload.get("tenant_id") or None,
                user_id=payload.get("sub"),
                organization_id=payload.get("organization_id") or None,
                roles=list(payload.get("roles") or []),
                auth_method="jwt",
            )
        except Exception as exc:
            logger.debug("JWT tenant resolve failed: %s", exc)
            return None

    async def _from_api_key(self, key_value: str, request: Request) -> Optional[TenantContext]:
        try:
            from app.api_key.service import ApiKeyService
            from app.db.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                record = await ApiKeyService(session).authenticate(key_value)
                if record is None:
                    return None
                org = request.headers.get("X-Organization-ID")
                return TenantContext(
                    tenant_id=str(record.tenant_id) if record.tenant_id else None,
                    user_id=None,
                    organization_id=org,
                    roles=["api_key"],
                    auth_method="api_key",
                    metadata={"api_key_id": record.id, "api_key_name": record.name},
                )
        except Exception as exc:
            logger.debug("API key resolve failed: %s", exc)
            return None
