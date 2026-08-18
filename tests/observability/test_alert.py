"""Tests for Alert Engine."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.observability.alert import AlertEngine
from app.observability.models import SystemEvent, SystemEventType


class TestAlertEngine:
    """AlertEngine unit and integration tests."""

    @pytest.mark.asyncio
    async def test_write_event_creates_system_event(self, db_session):
        engine = AlertEngine(db_session)
        ev = await engine.write_event(
            event_type=SystemEventType.ALERT.value,
            component="test-component",
            message="Test alert message",
            severity="warning",
        )
        assert ev.id is not None
        assert ev.event_type == "alert"
        assert ev.component == "test-component"

    @pytest.mark.asyncio
    async def test_write_event_persists(self, db_session):
        engine = AlertEngine(db_session)
        await engine.write_event(
            event_type="error",
            component="llm",
            message="LLM failure rate high",
            details={"rate": 0.1},
        )
        result = await db_session.execute(
            select(SystemEvent).where(SystemEvent.component == "llm")
        )
        events = list(result.scalars().all())
        assert len(events) >= 1
        assert events[0].message == "LLM failure rate high"

    @pytest.mark.asyncio
    async def test_write_event_with_tenant_id(self, db_session):
        engine = AlertEngine(db_session)
        ev = await engine.write_event(
            event_type="warning",
            component="sync",
            message="Sync delayed",
            tenant_id="t-tenant-1",
        )
        assert ev.tenant_id == "t-tenant-1"

    @pytest.mark.asyncio
    async def test_evaluate_all_returns_list(self, db_session):
        engine = AlertEngine(db_session)
        events = await engine.evaluate_all()
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_default_event_type_info(self, db_session):
        engine = AlertEngine(db_session)
        ev = await engine.write_event(
            component="test",
            message="Default type test",
        )
        assert ev.event_type == "info"

    @pytest.mark.asyncio
    async def test_write_event_error_type(self, db_session):
        engine = AlertEngine(db_session)
        ev = await engine.write_event(
            event_type="error",
            component="database",
            message="Connection timeout",
        )
        assert ev.severity == "info"  # default severity


class TestAlertEdgeCases:
    """Edge cases for alerts."""

    def test_system_event_type_values(self):
        assert SystemEventType.INFO.value == "info"
        assert SystemEventType.WARNING.value == "warning"
        assert SystemEventType.ERROR.value == "error"
        assert SystemEventType.ALERT.value == "alert"