"""OpenTelemetry Trace Manager.

Safe no-op when opentelemetry packages are not installed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider as SDKTraceProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

from app.tenant.context import get_tenant_context

logger = logging.getLogger(__name__)


class TraceManager:
    """Manage OpenTelemetry tracing lifecycle.

    Gracefully degrades when OTEL packages are missing.
    """

    _initialized: bool = False

    @classmethod
    def initialize(cls, *, service_name: str = "enterprise-knowledge-agent") -> None:
        if cls._initialized or not _OTEL_AVAILABLE:
            cls._initialized = True
            return
        try:
            provider = SDKTraceProvider()
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter())
            )
            otel_trace.set_tracer_provider(provider)
            logger.info("OpenTelemetry tracer initialized for %s", service_name)
        except Exception as exc:
            logger.warning("OpenTelemetry init failed (non-fatal): %s", exc)
        cls._initialized = True

    @staticmethod
    def start_span(
        name: str,
        *,
        attributes: Optional[Dict[str, Any]] = None,
        kind: Any = None,
    ) -> Any:
        """Start a new span, returning a no-op span if OTEL unavailable."""
        attrs = dict(attributes or {})
        ctx = get_tenant_context()
        if ctx:
            if ctx.tenant_id:
                attrs.setdefault("tenant_id", ctx.tenant_id)
            if ctx.user_id:
                attrs.setdefault("user_id", ctx.user_id)

        if _OTEL_AVAILABLE:
            tracer = otel_trace.get_tracer(__name__)
            return tracer.start_as_current_span(name, attributes=attrs, kind=kind)
        else:
            return _NoopSpan()

    @staticmethod
    def current_span() -> Any:
        if _OTEL_AVAILABLE:
            return otel_trace.get_current_span()
        return _NoopSpan()

    @staticmethod
    def get_trace_id() -> Optional[str]:
        if _OTEL_AVAILABLE:
            span = otel_trace.get_current_span()
            ctx = otel_trace.get_current_span().get_span_context() if span else None
            if ctx and ctx.trace_id:
                return format(ctx.trace_id, "032x")
        return None

    @staticmethod
    def get_span_id() -> Optional[str]:
        if _OTEL_AVAILABLE:
            span = otel_trace.get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.span_id:
                return format(ctx.span_id, "016x")
        return None


class _NoopSpan:
    """Context manager that does nothing."""

    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: Any = None) -> None:
        pass

    def get_span_context(self) -> None:
        return None


# Module-level shortcuts
def otel_tracer() -> Any:
    if _OTEL_AVAILABLE:
        import opentelemetry.trace as _t

        return _t.get_tracer(__name__)
    return None


def get_otel_tracer() -> Any:
    return otel_tracer()
