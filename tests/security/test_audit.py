"""Audit log tests."""

from __future__ import annotations

import pytest

from app.audit.service import AuditEvent
from app.tenant.context import TenantContext, clear_tenant_context, set_tenant_context


class TestAuditEvent:
    @pytest.mark.asyncio
    async def test_record_and_list(self, db_session) -> None:
        token = set_tenant_context(
            TenantContext(tenant_id="t1", user_id="u1")
        )
        try:
            evt = AuditEvent(db_session)
            log = await evt.record(
                "auth.login",
                resource="user",
                resource_id="u1",
                ip="127.0.0.1",
                details={"ok": True},
            )
            assert log.id
            assert log.tenant_id == "t1"
            logs = await evt.list_logs(tenant_id="t1")
            assert len(logs) >= 1
            assert logs[0].to_dict()["action"] == "auth.login"
        finally:
            clear_tenant_context(token)

    @pytest.mark.asyncio
    async def test_filter_by_action(self, db_session) -> None:
        evt = AuditEvent(db_session)
        await evt.record("agent.execute", tenant_id="t1")
        await evt.record("connector.sync", tenant_id="t1")
        logs = await evt.list_logs(tenant_id="t1", action="agent.execute")
        assert all(l.action == "agent.execute" for l in logs)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action",
        [
            "auth.login",
            "api_key.create",
            "api_key.revoke",
            "api_key.rotate",
            "agent.execute",
            "connector.sync",
            "document.delete",
            "permission.update",
        ],
    )
    async def test_sensitive_actions(self, db_session, action: str) -> None:
        evt = AuditEvent(db_session)
        log = await evt.record(action, tenant_id="t1", resource="x")
        assert log.action == action

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, db_session) -> None:
        evt = AuditEvent(db_session)
        await evt.record("auth.login", tenant_id="t1")
        await evt.record("auth.login", tenant_id="t2")
        logs = await evt.list_logs(tenant_id="t1")
        assert all(l.tenant_id == "t1" for l in logs)


class TestAuditAPI:
    @pytest.mark.asyncio
    async def test_list_logs_authed(self, auth_client) -> None:
        client, ctx = auth_client
        # generate via api key create which writes audit
        await client.post("/api/api-keys", json={"name": "aud"})
        resp = await client.get("/api/audit/logs")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_audit_no_auth(self, api_client) -> None:
        assert (await api_client.get("/api/audit/logs")).status_code in (401, 403)
