"""API Key service — create / revoke / rotate / authenticate."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_key.models import ApiKey, ApiKeyStatus
from app.tenant.isolation import apply_tenant_filter


class ApiKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_raw_key() -> Tuple[str, str]:
        """Return (raw_key, prefix). Format: ek_<prefix>_<secret>."""
        prefix = secrets.token_hex(4)
        secret = secrets.token_urlsafe(24)
        raw = f"ek_{prefix}_{secret}"
        return raw, prefix

    async def create(
        self,
        *,
        tenant_id: str,
        name: str,
        created_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Tuple[ApiKey, str]:
        raw, prefix = self._generate_raw_key()
        record = ApiKey(
            tenant_id=tenant_id,
            name=name,
            key_prefix=prefix,
            key_hash=self._hash_key(raw),
            status=ApiKeyStatus.ACTIVE.value,
            expires_at=expires_at,
            created_by=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record, raw

    async def revoke(self, key_id: str, *, tenant_id: Optional[str] = None) -> Optional[ApiKey]:
        key = await self.get(key_id, tenant_id=tenant_id)
        if key is None:
            return None
        key.status = ApiKeyStatus.REVOKED.value
        await self._session.flush()
        return key

    async def rotate(
        self, key_id: str, *, tenant_id: Optional[str] = None
    ) -> Optional[Tuple[ApiKey, str]]:
        key = await self.get(key_id, tenant_id=tenant_id)
        if key is None:
            return None
        raw, prefix = self._generate_raw_key()
        key.key_prefix = prefix
        key.key_hash = self._hash_key(raw)
        key.status = ApiKeyStatus.ACTIVE.value
        key.last_used_at = None
        await self._session.flush()
        return key, raw

    async def get(self, key_id: str, *, tenant_id: Optional[str] = None) -> Optional[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.id == key_id)
        stmt = apply_tenant_filter(stmt, ApiKey.tenant_id, tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, tenant_id: Optional[str] = None, limit: int = 50) -> List[ApiKey]:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc()).limit(limit)
        stmt = apply_tenant_filter(stmt, ApiKey.tenant_id, tenant_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def authenticate(self, raw_key: str) -> Optional[ApiKey]:
        """Validate raw key; update last_used_at on success."""
        if not raw_key or not raw_key.startswith("ek_"):
            return None
        parts = raw_key.split("_", 2)
        if len(parts) < 3:
            return None
        prefix = parts[1]
        digest = self._hash_key(raw_key)
        stmt = select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.key_hash == digest,
            ApiKey.status == ApiKeyStatus.ACTIVE.value,
        )
        result = await self._session.execute(stmt)
        key = result.scalar_one_or_none()
        if key is None:
            return None
        if key.expires_at is not None:
            exp = key.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                key.status = ApiKeyStatus.EXPIRED.value
                await self._session.flush()
                return None
        key.last_used_at = datetime.now(timezone.utc)
        await self._session.flush()
        return key
