"""Tenant request context (contextvars-based)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TenantContext:
    """Per-request tenant / user identity.

    Attributes:
        tenant_id: Current tenant UUID string.
        user_id: Authenticated user id.
        organization_id: Optional organization id.
        roles: Role names.
        auth_method: jwt | api_key | anonymous
        metadata: Extra request-scoped data.
    """

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    roles: list[str] = field(default_factory=list)
    auth_method: str = "anonymous"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "roles": list(self.roles),
            "auth_method": self.auth_method,
            "metadata": dict(self.metadata),
        }


_tenant_ctx: ContextVar[Optional[TenantContext]] = ContextVar("tenant_context", default=None)


def get_tenant_context() -> Optional[TenantContext]:
    """Return the current TenantContext or None."""
    return _tenant_ctx.get()


def get_tenant_id() -> Optional[str]:
    """Shortcut for current tenant_id."""
    ctx = _tenant_ctx.get()
    return ctx.tenant_id if ctx else None


def get_user_id() -> Optional[str]:
    """Shortcut for current user_id."""
    ctx = _tenant_ctx.get()
    return ctx.user_id if ctx else None


def get_organization_id() -> Optional[str]:
    """Shortcut for current organization_id."""
    ctx = _tenant_ctx.get()
    return ctx.organization_id if ctx else None


def set_tenant_context(ctx: TenantContext) -> Token:
    """Bind TenantContext for the current task/request."""
    return _tenant_ctx.set(ctx)


def clear_tenant_context(token: Optional[Token] = None) -> None:
    """Reset tenant context."""
    if token is not None:
        _tenant_ctx.reset(token)
    else:
        _tenant_ctx.set(None)


def require_tenant_id() -> str:
    """Return tenant_id or raise PermissionException."""
    from app.core.exceptions import PermissionDenied

    tid = get_tenant_id()
    if not tid:
        raise PermissionDenied(
            message="Tenant context required",
            details={"reason": "missing_tenant"},
        )
    return tid
