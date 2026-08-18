"""Tenant isolation helpers for ORM queries."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.sql import ColumnElement

from app.tenant.context import get_tenant_id


def resolve_tenant_id(
    tenant_id: Optional[str] = None,
    *,
    strict: bool = False,
) -> Optional[str]:
    """Resolve effective tenant id from argument or TenantContext.

    Args:
        tenant_id: Explicit tenant override.
        strict: If True and no tenant available, raise.

    Returns:
        Tenant id string or None (compat mode).
    """
    tid = tenant_id if tenant_id is not None else get_tenant_id()
    if strict and not tid:
        from app.core.exceptions import PermissionDenied

        raise PermissionDenied(
            message="Tenant isolation requires tenant_id",
            details={"strict": True},
        )
    return tid


def apply_tenant_filter(
    stmt: Any,
    column: ColumnElement[Any],
    tenant_id: Optional[str] = None,
    *,
    strict: bool = False,
) -> Any:
    """Append ``column == tenant_id`` when a tenant is known.

    When no tenant is in context and ``strict=False``, returns stmt unchanged
    for backward compatibility with legacy / test callers.
    """
    tid = resolve_tenant_id(tenant_id, strict=strict)
    if tid is None:
        return stmt
    return stmt.where(column == tid)


def assert_tenant_owns(
    resource_tenant_id: Optional[str],
    *,
    tenant_id: Optional[str] = None,
    resource: str = "resource",
) -> None:
    """Raise if resource belongs to another tenant.

    Skips check when current tenant context is empty (compat).
    """
    current = resolve_tenant_id(tenant_id, strict=False)
    if not current:
        return
    if resource_tenant_id is None:
        return
    if str(resource_tenant_id) != str(current):
        from app.core.exceptions import PermissionDenied

        raise PermissionDenied(
            message=f"Cross-tenant access denied for {resource}",
            details={
                "resource": resource,
                "resource_tenant_id": str(resource_tenant_id),
                "current_tenant_id": str(current),
            },
        )
