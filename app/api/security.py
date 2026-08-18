"""Security / SaaS management APIs: users, roles, permissions, api-keys, audit, quota."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_key.service import ApiKeyService
from app.audit.service import AuditEvent
from app.auth.dependencies import get_current_user, require_permission
from app.auth.models import PERMISSION_CODES, Role
from app.auth.organization import Organization, OrganizationType
from app.auth.repository import UserRepository
from app.core.exceptions import InvalidParameter
from app.db.session import get_db
from app.quota.service import QuotaService
from app.tenant.context import get_tenant_id

router = APIRouter(tags=["Enterprise Security"])


# ── Schemas ──


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class SetQuotaPlanRequest(BaseModel):
    plan: str = Field(..., pattern="^(free|pro|enterprise)$")
    tenant_id: Optional[str] = None


class CreateOrgRequest(BaseModel):
    name: str
    org_type: str = OrganizationType.ENTERPRISE.value
    parent_id: Optional[str] = None
    tenant_id: Optional[str] = None
    description: Optional[str] = None


# ── Users / Roles / Permissions ──


@router.get("/api/users")
async def list_users(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("admin.users")),
) -> Dict[str, Any]:
    tid = tenant_id or (current_user or {}).get("tenant_id") or get_tenant_id()
    repo = UserRepository(session)
    users = await repo.list_users(tenant_id=tid, limit=limit)
    return {
        "success": True,
        "data": [
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "tenant_id": str(u.tenant_id) if u.tenant_id else None,
                "roles": [r.name for r in (u.roles or [])],
            }
            for u in users
        ],
    }


@router.get("/api/roles")
async def list_roles(
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("admin.users")),
) -> Dict[str, Any]:
    result = await session.execute(select(Role).order_by(Role.name.asc()))
    roles = result.scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "permissions": [p.code for p in (r.permissions or [])],
            }
            for r in roles
        ],
    }


@router.get("/api/permissions")
async def list_permissions(
    _=Depends(require_permission("admin.users")),
) -> Dict[str, Any]:
    return {
        "success": True,
        "data": [{"code": c, "description": d} for c, d in PERMISSION_CODES.items()],
    }


# ── Organizations ──


@router.post("/api/organizations")
async def create_organization(
    body: CreateOrgRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("admin.tenant")),
) -> Dict[str, Any]:
    import uuid as uuid_mod

    tid = body.tenant_id or (current_user or {}).get("tenant_id") or get_tenant_id()
    if not tid:
        raise InvalidParameter(message="tenant_id is required")
    org = Organization(
        tenant_id=uuid_mod.UUID(str(tid)),
        parent_id=uuid_mod.UUID(body.parent_id) if body.parent_id else None,
        name=body.name.strip(),
        org_type=body.org_type,
        description=body.description,
    )
    session.add(org)
    await session.flush()
    return {"success": True, "data": org.to_dict()}


@router.get("/api/organizations")
async def list_organizations(
    tenant_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("admin.tenant")),
) -> Dict[str, Any]:
    import uuid as uuid_mod

    tid = tenant_id or (current_user or {}).get("tenant_id") or get_tenant_id()
    stmt = select(Organization).order_by(Organization.created_at.desc())
    if tid:
        stmt = stmt.where(Organization.tenant_id == uuid_mod.UUID(str(tid)))
    result = await session.execute(stmt)
    return {"success": True, "data": [o.to_dict() for o in result.scalars().all()]}


# ── API Keys ──


@router.post("/api/api-keys")
async def create_api_key(
    body: CreateApiKeyRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("apikey.manage")),
) -> Dict[str, Any]:
    tid = (current_user or {}).get("tenant_id") or get_tenant_id()
    if not tid:
        raise InvalidParameter(message="tenant_id required")
    svc = ApiKeyService(session)
    record, raw = await svc.create(
        tenant_id=str(tid),
        name=body.name.strip(),
        created_by=(current_user or {}).get("id"),
    )
    await AuditEvent(session).record(
        "api_key.create",
        resource="api_key",
        resource_id=record.id,
        ip=getattr(request.state, "client_ip", None),
        details={"name": record.name},
    )
    data = record.to_dict()
    data["api_key"] = raw  # shown once
    return {"success": True, "data": data}


@router.get("/api/api-keys")
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("apikey.manage")),
) -> Dict[str, Any]:
    tid = (current_user or {}).get("tenant_id") or get_tenant_id()
    keys = await ApiKeyService(session).list(tenant_id=tid)
    return {"success": True, "data": [k.to_dict() for k in keys]}


@router.post("/api/api-keys/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("apikey.manage")),
) -> Dict[str, Any]:
    tid = (current_user or {}).get("tenant_id") or get_tenant_id()
    key = await ApiKeyService(session).revoke(key_id, tenant_id=tid)
    if key is None:
        raise InvalidParameter(message="API key not found")
    await AuditEvent(session).record(
        "api_key.revoke",
        resource="api_key",
        resource_id=key_id,
        ip=getattr(request.state, "client_ip", None),
    )
    return {"success": True, "data": key.to_dict()}


@router.post("/api/api-keys/{key_id}/rotate")
async def rotate_api_key(
    key_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("apikey.manage")),
) -> Dict[str, Any]:
    tid = (current_user or {}).get("tenant_id") or get_tenant_id()
    result = await ApiKeyService(session).rotate(key_id, tenant_id=tid)
    if result is None:
        raise InvalidParameter(message="API key not found")
    key, raw = result
    await AuditEvent(session).record(
        "api_key.rotate",
        resource="api_key",
        resource_id=key_id,
        ip=getattr(request.state, "client_ip", None),
    )
    data = key.to_dict()
    data["api_key"] = raw
    return {"success": True, "data": data}


# ── Audit ──


@router.get("/api/audit/logs")
async def list_audit_logs(
    action: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("audit.read")),
) -> Dict[str, Any]:
    tid = (current_user or {}).get("tenant_id") or get_tenant_id()
    logs = await AuditEvent(session).list_logs(
        tenant_id=tid, action=action, limit=limit, offset=offset
    )
    return {"success": True, "data": [x.to_dict() for x in logs]}


# ── Quota ──


@router.get("/api/quota/status")
async def quota_status(
    tenant_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("quota.read")),
) -> Dict[str, Any]:
    tid = tenant_id or (current_user or {}).get("tenant_id") or get_tenant_id()
    if not tid:
        raise InvalidParameter(message="tenant_id required")
    status = await QuotaService(session).status(str(tid))
    return {"success": True, "data": status}


@router.post("/api/quota/plan")
async def set_quota_plan(
    body: SetQuotaPlanRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("admin.manage")),
) -> Dict[str, Any]:
    tid = body.tenant_id or (current_user or {}).get("tenant_id") or get_tenant_id()
    if not tid:
        raise InvalidParameter(message="tenant_id required")
    row = await QuotaService(session).set_plan(str(tid), body.plan)
    return {"success": True, "data": row.to_dict()}
