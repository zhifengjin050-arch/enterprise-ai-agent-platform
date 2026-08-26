"""Tests for LLM Usage Tracking (Phase 8)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.observability.cost_tracker import LLMUsageTracker
from app.observability.models import LLMUsageRecord, SystemEvent


class TestLLMUsageTracker:
    """LLMUsageTracker unit and integration tests."""

    @pytest.mark.asyncio
    async def test_record_creates_usage_record(self, db_session):
        tracker = LLMUsageTracker(db_session)
        record = await tracker.record(
            provider="deepseek",
            model="deepseek-chat",
            request_type="chat",
            prompt_tokens=100,
            completion_tokens=50,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert record.id is not None
        assert record.total_tokens == 150
        assert record.estimated_cost > 0

    @pytest.mark.asyncio
    async def test_record_persists_to_db(self, db_session):
        tracker = LLMUsageTracker(db_session)
        await tracker.record(
            provider="openai",
            model="gpt-4",
            prompt_tokens=500,
            completion_tokens=200,
        )
        result = await db_session.execute(select(LLMUsageRecord))
        rows = list(result.scalars().all())
        assert len(rows) >= 1

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, db_session):
        tracker = LLMUsageTracker(db_session)
        await tracker.record(tenant_id="t1", model="deepseek-chat", prompt_tokens=10)
        await tracker.record(tenant_id="t2", model="deepseek-chat", prompt_tokens=20)

        t1_records = await tracker.query(tenant_id="t1")
        assert len(t1_records) >= 1
        for r in t1_records:
            assert r.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_query_by_agent(self, db_session):
        tracker = LLMUsageTracker(db_session)
        await tracker.record(agent_id="a1", model="deepseek-chat", prompt_tokens=30)
        result = await tracker.query(agent_id="a1")
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_summary_returns_aggregates(self, db_session):
        tracker = LLMUsageTracker(db_session)
        await tracker.record(
            tenant_id="t-sum", model="deepseek-chat", prompt_tokens=100, completion_tokens=50
        )
        await tracker.record(
            tenant_id="t-sum", model="gpt-4", prompt_tokens=200, completion_tokens=100
        )

        summary = await tracker.summary(tenant_id="t-sum")
        assert summary["total_calls"] >= 2
        assert summary["total_tokens"] >= 450
        assert summary["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_summary_empty_tenant(self, db_session):
        tracker = LLMUsageTracker(db_session)
        summary = await tracker.summary(tenant_id="nonexistent")
        assert summary["total_calls"] == 0
        assert summary["total_tokens"] == 0
        assert summary["total_cost"] == 0.0

    @pytest.mark.asyncio
    async def test_zero_tokens_no_error(self, db_session):
        tracker = LLMUsageTracker(db_session)
        record = await tracker.record(
            provider="test",
            model="test-model",
            prompt_tokens=0,
            completion_tokens=0,
        )
        assert record.total_tokens == 0
        assert record.estimated_cost == 0.0


class TestCostEdgeCases:
    """Edge cases for cost tracking."""

    def test_estimate_tokens_method(self):
        from app.llm.cost.tracker import CostTracker

        tokens = CostTracker.estimate_tokens("Hello world")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_empty(self):
        from app.llm.cost.tracker import CostTracker

        tokens = CostTracker.estimate_tokens("")
        assert tokens == 1  # max(1, ...)

    def test_estimate_tokens_long_text(self):
        from app.llm.cost.tracker import CostTracker

        tokens = CostTracker.estimate_tokens("A" * 300)
        assert tokens == 100


class TestLLMUsageRecordModel:
    """LLMUsageRecord model standalone tests."""

    def test_default_fields(self):
        r = LLMUsageRecord(provider="unknown")
        assert r.tenant_id is None
        assert r.user_id is None
        assert r.agent_id is None
        assert r.task_id is None

    def test_to_dict_includes_created_at(self):
        from datetime import datetime, timezone

        r = LLMUsageRecord(created_at=datetime.now(timezone.utc))
        d = r.to_dict()
        assert "created_at" in d


class TestSystemEventModel:
    """SystemEvent model tests."""

    def test_default_event_type(self):
        e = SystemEvent(event_type="info")
        assert e.event_type == "info"

    def test_alert_event(self):
        e = SystemEvent(event_type="alert", component="test", message="alert msg")
        assert e.event_type == "alert"
        assert e.to_dict()["event_type"] == "alert"
