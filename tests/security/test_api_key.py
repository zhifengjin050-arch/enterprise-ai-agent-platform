"""API Key tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.api_key.models import ApiKeyStatus
from app.api_key.service import ApiKeyService
from app.tenant.context import TenantContext, clear_tenant_context, set_tenant_context
from app.tenant.middleware import TenantMiddleware


class TestApiKeyService:
    @pytest.mark.asyncio
    async def test_create_and_authenticate(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        record, raw = await svc.create(tenant_id="t1", name="ci")
        assert raw.startswith("ek_")
        assert record.key_prefix
        found = await svc.authenticate(raw)
        assert found is not None
        assert found.id == record.id
        assert found.last_used_at is not None

    @pytest.mark.asyncio
    async def test_authenticate_bad(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        assert await svc.authenticate("ek_dead_beef") is None
        assert await svc.authenticate("") is None
        assert await svc.authenticate("not-a-key") is None

    @pytest.mark.asyncio
    async def test_revoke(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        record, raw = await svc.create(tenant_id="t1", name="x")
        await svc.revoke(record.id, tenant_id="t1")
        assert await svc.authenticate(raw) is None

    @pytest.mark.asyncio
    async def test_rotate(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        record, raw1 = await svc.create(tenant_id="t1", name="x")
        result = await svc.rotate(record.id, tenant_id="t1")
        assert result is not None
        key, raw2 = result
        assert raw1 != raw2
        assert await svc.authenticate(raw1) is None
        assert await svc.authenticate(raw2) is not None

    @pytest.mark.asyncio
    async def test_expired(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        record, raw = await svc.create(
            tenant_id="t1",
            name="exp",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert await svc.authenticate(raw) is None
        refreshed = await svc.get(record.id, tenant_id="t1")
        assert refreshed.status == ApiKeyStatus.EXPIRED.value

    @pytest.mark.asyncio
    async def test_list_tenant_isolation(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        await svc.create(tenant_id="t1", name="a")
        await svc.create(tenant_id="t2", name="b")
        keys = await svc.list(tenant_id="t1")
        assert all(k.tenant_id == "t1" for k in keys)

    @pytest.mark.asyncio
    async def test_to_dict(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        record, _ = await svc.create(tenant_id="t1", name="n")
        d = record.to_dict()
        assert d["name"] == "n"
        assert "key_hash" not in d


class TestApiKeyAPI:
    @pytest.mark.asyncio
    async def test_create_list_revoke_rotate(self, auth_client) -> None:
        client, _ = auth_client
        created = await client.post("/api/api-keys", json={"name": "prod"})
        assert created.status_code == 200, created.text
        data = created.json()["data"]
        assert "api_key" in data
        key_id = data["id"]

        listed = await client.get("/api/api-keys")
        assert listed.status_code == 200
        assert any(k["id"] == key_id for k in listed.json()["data"])

        rotated = await client.post(f"/api/api-keys/{key_id}/rotate")
        assert rotated.status_code == 200
        assert "api_key" in rotated.json()["data"]

        revoked = await client.post(f"/api/api-keys/{key_id}/revoke")
        assert revoked.status_code == 200
        assert revoked.json()["data"]["status"] == "revoked"

    @pytest.mark.asyncio
    async def test_api_keys_no_auth(self, api_client) -> None:
        assert (await api_client.get("/api/api-keys")).status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_middleware_resolves_api_key(self, db_session) -> None:
        svc = ApiKeyService(db_session)
        record, raw = await svc.create(tenant_id="tenant-xyz", name="mw")
        await db_session.commit()

        # Direct service path used by middleware
        found = await svc.authenticate(raw)
        assert found is not None
        assert found.tenant_id == "tenant-xyz"

        token = set_tenant_context(
            TenantContext(
                tenant_id=found.tenant_id,
                auth_method="api_key",
                metadata={"api_key_id": found.id},
            )
        )
        try:
            from app.tenant.context import get_tenant_id

            assert get_tenant_id() == "tenant-xyz"
        finally:
            clear_tenant_context(token)
