"""Workflow Observability Integration — Phase 9.

Injects tracing, metrics, and audit logging into workflow executions.
Records workflow_id, node_id, and tenant_id for every significant event.

Metrics are registered at import time on the shared Phase 8 registry
to avoid duplicate-registration errors at runtime.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Prometheus metrics (registered once at import)
# ──────────────────────────────────────────────

_workflow_count: Any = None
_workflow_duration: Any = None
_workflow_node_count: Any = None

try:
    from prometheus_client import Counter, Histogram

    # Use Phase 8's dedicated registry to avoid conflicts
    from app.observability.metrics import _OBSERVABILITY_REGISTRY as _wf_registry

    if _wf_registry is not None:
        _workflow_count = Counter(
            "workflow_execution_total",
            "Total workflow executions",
            labelnames=["status", "trigger_type", "tenant_id"],
            registry=_wf_registry,
        )
        _workflow_duration = Histogram(
            "workflow_execution_duration_seconds",
            "Workflow execution duration in seconds",
            labelnames=["workflow_id", "status"],
            registry=_wf_registry,
        )
        _workflow_node_count = Counter(
            "workflow_node_execution_total",
            "Total workflow node executions",
            labelnames=["node_type", "status", "tenant_id"],
            registry=_wf_registry,
        )
except Exception as exc:
    logger.debug("Workflow metrics registration skipped: %s", exc)

# ──────────────────────────────────────────────
# Tracing
# ──────────────────────────────────────────────


def record_workflow_trace(
    workflow_id: str,
    run_id: str,
    node_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Record a workflow trace event via OpenTelemetry if available.

    Gracefully degrades if OpenTelemetry is not configured.
    """
    try:
        from app.observability.trace import TraceManager

        tracer = TraceManager.get_tracer()
        if tracer is None:
            return

        attrs: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "workflow.status": status or "unknown",
        }
        if node_name:
            attrs["workflow.node_name"] = node_name
        if tenant_id:
            attrs["tenant_id"] = tenant_id
        if error:
            attrs["workflow.error"] = error

        with tracer.start_as_current_span(
            f"workflow.{node_name or 'execute'}",
            attributes=attrs,
        ) as span:
            if error:
                span.set_status(status_code=2, description=error)  # STATUS_CODE_ERROR
    except Exception as exc:
        logger.debug("Workflow trace recording skipped: %s", exc)


def inc_workflow_exec_count(
    status: str = "completed",
    trigger_type: str = "api",
    tenant_id: Optional[str] = None,
) -> None:
    """Increment the workflow execution counter."""
    if _workflow_count is not None:
        try:
            _workflow_count.labels(
                status=status,
                trigger_type=trigger_type,
                tenant_id=tenant_id or "none",
            ).inc()
        except Exception as exc:
            logger.debug("Workflow count metric skipped: %s", exc)


def observe_workflow_duration(
    seconds: float,
    workflow_id: str = "",
    status: str = "completed",
) -> None:
    """Record workflow execution duration."""
    if _workflow_duration is not None:
        try:
            _workflow_duration.labels(
                workflow_id=workflow_id,
                status=status,
            ).observe(seconds)
        except Exception as exc:
            logger.debug("Workflow duration metric skipped: %s", exc)


def inc_workflow_node_count(
    node_type: str = "unknown",
    status: str = "success",
    tenant_id: Optional[str] = None,
) -> None:
    """Increment the workflow node execution counter."""
    if _workflow_node_count is not None:
        try:
            _workflow_node_count.labels(
                node_type=node_type,
                status=status,
                tenant_id=tenant_id or "none",
            ).inc()
        except Exception as exc:
            logger.debug("Workflow node metric skipped: %s", exc)


# ──────────────────────────────────────────────
# Audit logging
# ──────────────────────────────────────────────


def log_workflow_event(
    workflow_id: str,
    run_id: str,
    event_type: str,
    node_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a structured audit log entry for a workflow event.

    This supplements database-level workflow_events with real-time log output.
    """
    extra: Dict[str, Any] = {
        "workflow_id": workflow_id,
        "run_id": run_id,
        "event_type": event_type,
        "tenant_id": tenant_id or "none",
    }
    if node_name:
        extra["node_name"] = node_name
    if data:
        extra["data"] = data

    logger.info(
        "Workflow event [%s] run=%s workflow=%s node=%s",
        event_type,
        run_id,
        workflow_id,
        node_name or "-",
        extra=extra,
    )
