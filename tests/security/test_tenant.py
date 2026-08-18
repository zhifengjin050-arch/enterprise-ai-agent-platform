"""Tenant context / isolation / middleware tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agent_runtime.models import AgentRecord
from app.core.exceptions import PermissionDenied
from app.tenant.context import (
    TenantContext,
    clear_tenant_context,
    get_tenant_context,
    get_tenant_id,
    get_user_id,
    require_tenant_id,
    set_tenant_context,
)
from app.tenant.isolation import apply_tenant_filter, assert_tenant_owns, resolve_tenant_id


class TestTenantContext:
    def test_set_get_clear(self) -> None:
        token = set_tenant_context(
            TenantContext(tenant_id="t1", user_id="u1", organization_id="o1")
        )
        try:
            ctx = get_tenant_context()
            assert ctx is not None
            assert get_tenant_id() == "t1"
            assert get_user_id() == "u1"
            assert ctx.organization_id == "o1"
            assert ctx.to_dict()["tenant_id"] == "t1"
        finally:
            clear_tenant_context(token)
        assert get_tenant_context() is None

    def test_require_tenant_raises(self) -> None:
        clear_tenant_context()
        with pytest.raises(PermissionDenied):
            require_tenant_id()

    def test_require_tenant_ok(self) -> None:
        token = set_tenant_context(TenantContext(tenant_id="t9"))
        try:
            assert require_tenant_id() == "t9"
        finally:
            clear_tenant_context(token)

    @pytest.mark.parametrize(
        "method",
        ["jwt", "api_key", "anonymous"],
    )
    def test_auth_methods(self, method: str) -> None:
        token = set_tenant_context(TenantContext(auth_method=method))
        try:
            assert get_tenant_context().auth_method == method
        finally:
            clear_tenant_context(token)


class TestIsolation:
    def test_resolve_prefers_arg(self) -> None:
        token = set_tenant_context(TenantContext(tenant_id="ctx"))
        try:
            assert resolve_tenant_id("explicit") == "explicit"
            assert resolve_tenant_id() == "ctx"
        finally:
            clear_tenant_context(token)

    def test_resolve_strict(self) -> None:
        clear_tenant_context()
        with pytest.raises(PermissionDenied):
            resolve_tenant_id(strict=True)

    def test_assert_tenant_owns(self) -> None:
        token = set_tenant_context(TenantContext(tenant_id="t1"))
        try:
            assert_tenant_owns("t1")
            with pytest.raises(PermissionDenied):
                assert_tenant_owns("t2", resource="doc")
        finally:
            clear_tenant_context(token)

    def test_assert_skips_without_context(self) -> None:
        clear_tenant_context()
        assert_tenant_owns("anything")  # no raise

    @pytest.mark.asyncio
    async def test_apply_tenant_filter(self, db_session) -> None:
        db_session.add(AgentRecord(name="A", agent_type="knowledge", tenant_id="t1"))
        db_session.add(AgentRecord(name="B", agent_type="knowledge", tenant_id="t2"))
        await db_session.flush()
        stmt = select(AgentRecord)
        filtered = apply_tenant_filter(stmt, AgentRecord.tenant_id, "t1")
        rows = (await db_session.execute(filtered)).scalars().all()
        assert len(rows) == 1
        assert rows[0].name == "A"

    @pytest.mark.asyncio
    async def test_apply_no_filter_without_tenant(self, db_session) -> None:
        clear_tenant_context()
        db_session.add(AgentRecord(name="A", agent_type="knowledge", tenant_id="t1"))
        db_session.add(AgentRecord(name="B", agent_type="knowledge", tenant_id="t2"))
        await db_session.flush()
        stmt = apply_tenant_filter(select(AgentRecord), AgentRecord.tenant_id, None)
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) >= 2


class TestOrgAPI:
    @pytest.mark.asyncio
    async def test_create_org(self, auth_client) -> None:
        client, ctx = auth_client
        resp = await client.post(
            "/api/organizations",
            json={
                "name": "Acme",
                "org_type": "enterprise",
                "tenant_id": str(ctx["tenant"].id),
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_list_orgs(self, auth_client) -> None:
        client, ctx = auth_client
        await client.post(
            "/api/organizations",
            json={"name": "Dept", "org_type": "department", "tenant_id": str(ctx["tenant"].id)},
        )
        resp = await client.get("/api/organizations")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1
