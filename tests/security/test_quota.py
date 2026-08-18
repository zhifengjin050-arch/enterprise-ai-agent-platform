"""Quota system tests."""

from __future__ import annotations

import pytest

from app.core.exceptions import LLMQuotaException
from app.quota.models import DEFAULT_PLANS, QuotaPlanName
from app.quota.service import QuotaService


class TestQuotaService:
    @pytest.mark.asyncio
    async def test_get_or_create_free(self, db_session) -> None:
        svc = QuotaService(db_session)
        row = await svc.get_or_create("t1")
        assert row.plan == "free"
        assert row.daily_tokens == DEFAULT_PLANS["free"]["daily_tokens"]

    @pytest.mark.asyncio
    async def test_status(self, db_session) -> None:
        svc = QuotaService(db_session)
        status = await svc.status("t1")
        assert status["tenant_id"] == "t1"
        assert "used_tokens" in status

    @pytest.mark.asyncio
    async def test_consume_tokens(self, db_session) -> None:
        svc = QuotaService(db_session)
        await svc.consume_tokens("t1", 10)
        row = await svc.get_or_create("t1")
        assert row.used_tokens == 10

    @pytest.mark.asyncio
    async def test_token_quota_exceeded(self, db_session) -> None:
        svc = QuotaService(db_session)
        row = await svc.get_or_create("t1")
        row.used_tokens = row.daily_tokens
        await db_session.flush()
        with pytest.raises(LLMQuotaException):
            await svc.check_tokens("t1", 1)

    @pytest.mark.asyncio
    async def test_agent_run_quota(self, db_session) -> None:
        svc = QuotaService(db_session)
        await svc.consume_agent_run("t1")
        row = await svc.get_or_create("t1")
        assert row.used_agent_runs == 1

    @pytest.mark.asyncio
    async def test_agent_quota_exceeded(self, db_session) -> None:
        svc = QuotaService(db_session)
        row = await svc.get_or_create("t1")
        row.used_agent_runs = row.daily_agent_runs
        await db_session.flush()
        with pytest.raises(LLMQuotaException):
            await svc.check_agent_run("t1")

    @pytest.mark.asyncio
    async def test_enterprise_unlimited(self, db_session) -> None:
        svc = QuotaService(db_session)
        await svc.set_plan("t1", QuotaPlanName.ENTERPRISE.value)
        # should not raise even with huge usage
        row = await svc.get_or_create("t1")
        row.used_tokens = 10**9
        await db_session.flush()
        await svc.check_tokens("t1", 1000)
        await svc.check_agent_run("t1")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan", ["free", "pro", "enterprise"])
    async def test_set_plans(self, db_session, plan: str) -> None:
        svc = QuotaService(db_session)
        row = await svc.set_plan("t-plan", plan)
        assert row.plan == plan
        assert row.unlimited == DEFAULT_PLANS[plan]["unlimited"]

    @pytest.mark.asyncio
    async def test_unknown_plan(self, db_session) -> None:
        svc = QuotaService(db_session)
        with pytest.raises(ValueError):
            await svc.set_plan("t1", "gold")

    @pytest.mark.asyncio
    async def test_daily_reset(self, db_session) -> None:
        svc = QuotaService(db_session)
        row = await svc.get_or_create("t1")
        row.used_tokens = 50
        row.usage_date = "2000-01-01"
        await db_session.flush()
        row2 = await svc.get_or_create("t1")
        assert row2.used_tokens == 0


class TestQuotaAPI:
    @pytest.mark.asyncio
    async def test_status_api(self, auth_client) -> None:
        client, _ = auth_client
        resp = await client.get("/api/quota/status")
        assert resp.status_code == 200
        assert resp.json()["data"]["plan"] in ("free", "pro", "enterprise")

    @pytest.mark.asyncio
    async def test_set_plan_api(self, auth_client) -> None:
        client, _ = auth_client
        resp = await client.post("/api/quota/plan", json={"plan": "pro"})
        assert resp.status_code == 200
        assert resp.json()["data"]["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_quota_no_auth(self, api_client) -> None:
        assert (await api_client.get("/api/quota/status")).status_code in (401, 403)
