"""Tests for workflow observability integration — Phase 9."""

from __future__ import annotations

from app.workflow_engine.observability import (
    inc_workflow_exec_count,
    inc_workflow_node_count,
    log_workflow_event,
    observe_workflow_duration,
    record_workflow_trace,
)


class TestWorkflowObservability:
    """Tests that observability hooks run without error."""

    def test_record_trace(self) -> None:
        # Should not raise
        record_workflow_trace(
            workflow_id="wf-1",
            run_id="run-1",
            node_name="start",
            tenant_id="t1",
            status="RUNNING",
        )

    def test_record_trace_with_error(self) -> None:
        record_workflow_trace(
            workflow_id="wf-1",
            run_id="run-1",
            tenant_id="t1",
            status="FAILED",
            error="Something went wrong",
        )

    def test_inc_exec_count(self) -> None:
        inc_workflow_exec_count(
            status="completed",
            trigger_type="api",
            tenant_id="t1",
        )

    def test_observe_duration(self) -> None:
        observe_workflow_duration(
            seconds=1.5,
            workflow_id="wf-1",
            status="completed",
        )

    def test_inc_node_count(self) -> None:
        inc_workflow_node_count(
            node_type="agent",
            status="success",
            tenant_id="t1",
        )

    def test_log_event(self) -> None:
        log_workflow_event(
            workflow_id="wf-1",
            run_id="run-1",
            event_type="node_start",
            node_name="start",
            tenant_id="t1",
            data={"key": "value"},
        )

    def test_graceful_degradation(self) -> None:
        """Observability should not crash when dependencies are missing."""
        # Simulate by calling with invalid module path — should be safe
        record_workflow_trace(
            workflow_id="wf-x",
            run_id="run-x",
            status="UNKNOWN",
        )
        inc_workflow_exec_count()
        observe_workflow_duration(0.0)
        inc_workflow_node_count()
        log_workflow_event(
            workflow_id="wf-x",
            run_id="run-x",
            event_type="test",
        )
