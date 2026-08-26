"""RBAC / PermissionChecker tests."""

from __future__ import annotations

import pytest

from app.auth.models import PERMISSION_CODES
from app.auth.rbac import PermissionChecker
from app.core.exceptions import PermissionDenied
from app.tenant.context import TenantContext, clear_tenant_context, set_tenant_context


class TestPermissionCodes:
    @pytest.mark.parametrize(
        "code",
        [
            "connector.read",
            "connector.write",
            "connector.sync",
            "knowledge.read",
            "knowledge.write",
            "agent.read",
            "agent.execute",
            "admin.manage",
            "audit.read",
            "quota.read",
            "apikey.manage",
        ],
    )
    def test_required_codes_present(self, code: str) -> None:
        assert code in PERMISSION_CODES


class TestPermissionChecker:
    @pytest.mark.asyncio
    async def test_empty_user_no_perms(self, db_session) -> None:
        checker = PermissionChecker(db_session)
        assert await checker.has("agent.execute", user_id=None) is False

    @pytest.mark.asyncio
    async def test_api_key_principal_has_defaults(self, db_session) -> None:
        token = set_tenant_context(TenantContext(tenant_id="t1", auth_method="api_key"))
        try:
            checker = PermissionChecker(db_session)
            assert await checker.has("agent.execute") is True
            assert await checker.has("knowledge.read") is True
            assert await checker.has("admin.manage") is False
        finally:
            clear_tenant_context(token)

    @pytest.mark.asyncio
    async def test_require_raises(self, db_session) -> None:
        checker = PermissionChecker(db_session)
        with pytest.raises(PermissionDenied):
            await checker.require("admin.manage", user_id=None)

    @pytest.mark.asyncio
    async def test_permission_codes_count(self) -> None:
        assert "admin.manage" in PERMISSION_CODES
        assert len(PERMISSION_CODES) >= 15

    @pytest.mark.asyncio
    async def test_admin_manage_grants_all(self, db_session) -> None:
        """If user only has admin.manage, has() returns True for others."""
        checker = PermissionChecker(db_session)

        async def _fake_get(uid):
            return {"admin.manage"}

        checker.get_permissions = _fake_get  # type: ignore
        assert await checker.has("agent.execute", user_id="x") is True


class TestSecurityAPIAuth:
    @pytest.mark.asyncio
    async def test_users_no_auth(self, api_client) -> None:
        assert (await api_client.get("/api/users")).status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_roles_no_auth(self, api_client) -> None:
        assert (await api_client.get("/api/roles")).status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_permissions_no_auth(self, api_client) -> None:
        assert (await api_client.get("/api/permissions")).status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_users_authed(self, auth_client) -> None:
        client, _ = auth_client
        resp = await client.get("/api/users")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_list_roles_authed(self, auth_client) -> None:
        client, _ = auth_client
        resp = await client.get("/api/roles")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_permissions_authed(self, auth_client) -> None:
        client, _ = auth_client
        resp = await client.get("/api/permissions")
        assert resp.status_code == 200
        codes = {p["code"] for p in resp.json()["data"]}
        assert "agent.execute" in codes
