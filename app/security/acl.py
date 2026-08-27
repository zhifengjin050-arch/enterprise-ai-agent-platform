"""Access control for knowledge retrieval.

ACL lives on document/chunk ``metadata`` (and optional ``metadata_json.acl``):

    {
      "acl": {
        "classification": "public" | "internal" | "confidential" | "secret",
        "tenant_id": "...",
        "allowed_org_ids": ["dept-finance"],
        "allowed_user_ids": ["user-uuid"]
      }
    }

Rules:
    * ``secret`` is never returned by RAG.
    * Non-empty allow-lists require a matching user or organization.
    * Tenant mismatch is denied when both sides have a tenant.
    * Unmarked documents stay tenant-visible (legacy / tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

SECRET_CLASSIFICATION = "secret"
_ADMIN_ROLES = {"admin", "superadmin", "owner"}


@dataclass(frozen=True)
class AccessPrincipal:
    """Caller identity used at query time."""

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    roles: tuple[str, ...] = ()

    @classmethod
    def from_context(cls) -> AccessPrincipal:
        from app.tenant.context import get_tenant_context

        ctx = get_tenant_context()
        if ctx is None:
            return cls()
        return cls(
            tenant_id=str(ctx.tenant_id) if ctx.tenant_id else None,
            user_id=str(ctx.user_id) if ctx.user_id else None,
            organization_id=str(ctx.organization_id) if ctx.organization_id else None,
            roles=tuple(str(r) for r in (ctx.roles or [])),
        )

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> AccessPrincipal:
        if not data:
            return cls()
        roles = data.get("roles") or ()
        return cls(
            tenant_id=_opt_str(data.get("tenant_id")),
            user_id=_opt_str(data.get("user_id") or data.get("id")),
            organization_id=_opt_str(data.get("organization_id")),
            roles=tuple(str(r) for r in roles),
        )

    def is_admin(self) -> bool:
        lowered = {r.lower() for r in self.roles}
        return bool(lowered & _ADMIN_ROLES)


@dataclass(frozen=True)
class DocumentACL:
    classification: str = "internal"
    tenant_id: Optional[str] = None
    allowed_org_ids: tuple[str, ...] = ()
    allowed_user_ids: tuple[str, ...] = ()

    @classmethod
    def from_metadata(cls, metadata: Optional[Mapping[str, Any]]) -> DocumentACL:
        blob: Mapping[str, Any] = metadata or {}
        nested = blob.get("acl") if isinstance(blob.get("acl"), Mapping) else None
        raw: Mapping[str, Any] = nested if nested is not None else blob
        org_val = raw.get("allowed_org_ids")
        if org_val is None:
            org_val = blob.get("acl_org_ids")
        user_val = raw.get("allowed_user_ids")
        if user_val is None:
            user_val = blob.get("acl_user_ids")
        orgs = _str_tuple(org_val)
        users = _str_tuple(user_val)
        classification = str(
            raw.get("classification")
            or blob.get("acl_classification")
            or blob.get("classification")
            or "internal"
        )
        tenant_id = _opt_str(
            raw.get("tenant_id") or blob.get("acl_tenant_id") or blob.get("tenant_id")
        )
        return cls(
            classification=classification.lower(),
            tenant_id=tenant_id,
            allowed_org_ids=orgs,
            allowed_user_ids=users,
        )

    def chroma_fields(self) -> dict[str, str]:
        """Chroma only accepts scalar metadata values."""
        return {
            "acl_classification": self.classification,
            "acl_tenant_id": self.tenant_id or "",
            "acl_org_ids": ",".join(self.allowed_org_ids),
            "acl_user_ids": ",".join(self.allowed_user_ids),
        }

    def to_metadata(self) -> dict[str, Any]:
        return {
            "acl": {
                "classification": self.classification,
                "tenant_id": self.tenant_id,
                "allowed_org_ids": list(self.allowed_org_ids),
                "allowed_user_ids": list(self.allowed_user_ids),
            }
        }


def principal_can_read(
    principal: AccessPrincipal, acl: DocumentACL | Mapping[str, Any] | None
) -> bool:
    """Return True if ``principal`` may see this document/chunk in RAG."""
    parsed = acl if isinstance(acl, DocumentACL) else DocumentACL.from_metadata(acl)
    if parsed.classification == SECRET_CLASSIFICATION:
        return False
    if parsed.allowed_user_ids:
        if principal.user_id and principal.user_id in parsed.allowed_user_ids:
            return True
        return principal.is_admin()
    if parsed.allowed_org_ids:
        if principal.organization_id and principal.organization_id in parsed.allowed_org_ids:
            return True
        return principal.is_admin()
    if parsed.tenant_id and principal.tenant_id:
        if str(parsed.tenant_id) != str(principal.tenant_id) and not principal.is_admin():
            return False
    return True


def filter_visible(
    items: Iterable[Any],
    principal: AccessPrincipal,
    *,
    metadata_attr: str = "metadata",
) -> list[Any]:
    """Drop items the principal must not see."""
    visible: list[Any] = []
    for item in items:
        meta = _item_metadata(item, metadata_attr)
        if principal_can_read(principal, meta):
            visible.append(item)
    return visible


def merge_acl_metadata(
    metadata: Optional[Mapping[str, Any]],
    acl: DocumentACL,
) -> dict[str, Any]:
    merged = dict(metadata or {})
    merged.update(acl.to_metadata())
    return merged


def _item_metadata(item: Any, metadata_attr: str) -> Mapping[str, Any]:
    if isinstance(item, Mapping):
        return item.get("metadata") or item.get("metadata_json") or item
    meta = getattr(item, metadata_attr, None)
    if meta is None:
        meta = getattr(item, "metadata_json", None)
    if isinstance(meta, Mapping):
        return meta
    return {}


def _opt_str(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return tuple(parts)
    return tuple(str(v) for v in value if v)
