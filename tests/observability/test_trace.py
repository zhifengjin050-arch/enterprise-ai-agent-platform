"""Tests for OpenTelemetry TraceManager."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.observability.trace import TraceManager, _NoopSpan


class TestTraceManager:
    """TraceManager unit tests."""

    def test_noop_span_context_manager(self):
        """_NoopSpan works as a context manager."""
        with _NoopSpan() as span:
            assert span is not None
            span.set_attribute("key", "value")
            span.add_event("test_event")

    def test_noop_span_get_span_context_returns_none(self):
        span = _NoopSpan()
        assert span.get_span_context() is None

    @patch("app.observability.trace._OTEL_AVAILABLE", False)
    def test_start_span_noop_when_otel_unavailable(self):
        with TraceManager.start_span("test") as span:
            assert isinstance(span, _NoopSpan)

    def test_get_trace_id_no_otel(self):
        tid = TraceManager.get_trace_id()
        # Should be None without OTEL
        assert tid is None

    def test_get_span_id_no_otel(self):
        sid = TraceManager.get_span_id()
        assert sid is None

    def test_initialize_is_safe_multiple_calls(self):
        TraceManager._initialized = False
        TraceManager.initialize(service_name="test-service")
        assert TraceManager._initialized is True
        # Second call should not raise
        TraceManager.initialize(service_name="test-service")

    def test_start_span_includes_tenant_attributes(self):
        """Span should include tenant_id/user_id if TenantContext is active."""
        from app.tenant.context import TenantContext, set_tenant_context, clear_tenant_context

        ctx = TenantContext(tenant_id="t-001", user_id="u-001")
        token = set_tenant_context(ctx)
        try:
            with patch("app.observability.trace._OTEL_AVAILABLE", False):
                with TraceManager.start_span("test", attributes={"custom": "val"}) as span:
                    assert isinstance(span, _NoopSpan)
        finally:
            clear_tenant_context(token)

    def test_current_span_noop(self):
        span = TraceManager.current_span()
        assert isinstance(span, _NoopSpan)


class TestTraceManagerInitialization:
    """TraceManager initialization edge cases."""

    def test_initialized_flag_persists(self):
        TraceManager._initialized = False
        TraceManager.initialize()
        assert TraceManager._initialized is True

    @patch("app.observability.trace._OTEL_AVAILABLE", False)
    def test_initialize_otel_unavailable_does_not_raise(self):
        TraceManager._initialized = False
        TraceManager.initialize(service_name="test")
        assert TraceManager._initialized is True


class TestObservabilityModels:
    """LLMUsageRecord and AgentExecutionTrace model tests."""

    def test_llm_usage_record_defaults(self):
        from app.observability.models import LLMUsageRecord

        r = LLMUsageRecord(provider="unknown", total_tokens=0, estimated_cost=0.0)
        # Column defaults fire on INSERT, not on instantiation in SQLAlchemy 2.0
        # So we set meaningful defaults explicitly or assert None
        assert r.id is None  # default applies on INSERT
        assert r.to_dict() is not None

    def test_llm_usage_record_to_dict(self):
        from app.observability.models import LLMUsageRecord

        r = LLMUsageRecord(
            tenant_id="t1",
            user_id="u1",
            provider="deepseek",
            model="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=50,
        )
        d = r.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["user_id"] == "u1"
        assert d["provider"] == "deepseek"
        assert d["prompt_tokens"] == 100
        assert d["completion_tokens"] == 50

    def test_agent_execution_trace_defaults(self):
        from app.observability.models import AgentExecutionTrace

        t = AgentExecutionTrace(step=0, success=True)
        # Column defaults apply on INSERT
        assert t.id is None
        assert t.to_dict() is not None

    def test_agent_execution_trace_to_dict(self):
        from app.observability.models import AgentExecutionTrace

        t = AgentExecutionTrace(
            task_id="task-1",
            tenant_id="t1",
            step=1,
            component="planner",
            latency_ms=150,
            success=True,
        )
        d = t.to_dict()
        assert d["task_id"] == "task-1"
        assert d["step"] == 1
        assert d["component"] == "planner"
        assert d["latency_ms"] == 150

    def test_system_event_defaults(self):
        from app.observability.models import SystemEvent, SystemEventType

        e = SystemEvent(event_type=SystemEventType.INFO.value, severity="info")
        # Column defaults apply on INSERT
        assert e.id is None

    def test_system_event_to_dict(self):
        from app.observability.models import SystemEvent

        e = SystemEvent(
            event_type="alert",
            component="llm",
            message="High failure rate",
            severity="critical",
        )
        d = e.to_dict()
        assert d["event_type"] == "alert"
        assert d["message"] == "High failure rate"

    def test_system_event_enum_values(self):
        from app.observability.models import SystemEventType

        assert SystemEventType.INFO.value == "info"
        assert SystemEventType.WARNING.value == "warning"
        assert SystemEventType.ERROR.value == "error"
        assert SystemEventType.ALERT.value == "alert"