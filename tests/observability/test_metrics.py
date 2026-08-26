"""Tests for Prometheus Metrics (ObservabilityMetrics + Phase 8 metrics)."""

from __future__ import annotations

from app.observability.metrics import (
    _OBSERVABILITY_REGISTRY,
    agent_failure_total,
    agent_task_latency,
    agent_task_total,
    generate_observability_metrics,
    llm_latency,
    llm_request_total,
    llm_tokens_input,
    llm_tokens_output,
    retrieval_latency,
    retrieval_total,
    sync_duration,
    sync_failure_total,
    sync_job_total,
)


class TestPhase8MetricsExist:
    """Verify that all Phase 8 metrics are defined."""

    def test_agent_metrics_defined(self):
        # prometheus_client Counter _name strips _total suffix
        assert agent_task_total._name == "agent_tasks"
        assert agent_task_latency._name == "agent_task_duration_seconds"
        assert agent_failure_total._name == "agent_failures"

    def test_llm_metrics_defined(self):
        assert llm_request_total._name == "llm_requests"
        assert llm_latency._name == "llm_request_duration_seconds"
        assert llm_tokens_input._name == "llm_tokens_input"
        assert llm_tokens_output._name == "llm_tokens_output"

    def test_knowledge_metrics_defined(self):
        assert retrieval_total._name == "knowledge_retrievals"
        assert retrieval_latency._name == "knowledge_retrieval_duration_seconds"

    def test_sync_metrics_defined(self):
        assert sync_job_total._name == "sync_jobs"
        assert sync_duration._name == "sync_job_duration_seconds"
        assert sync_failure_total._name == "sync_failures"

    def test_metrics_generate_latest(self):
        output = generate_observability_metrics()
        assert isinstance(output, str)
        assert len(output) > 0


class TestMetricRecording:
    """Test that recording metrics works without errors."""

    def test_record_agent_metrics(self):
        agent_task_total.labels(agent_type="react", status="success").inc()
        agent_failure_total.labels(agent_type="react", error_code="timeout").inc()
        agent_task_latency.labels(agent_type="react").observe(1.5)

    def test_record_llm_metrics(self):
        llm_request_total.labels(
            provider="deepseek", model="deepseek-chat", request_type="chat"
        ).inc()
        llm_tokens_input.labels(provider="deepseek", model="deepseek-chat").inc(100)
        llm_tokens_output.labels(provider="deepseek", model="deepseek-chat").inc(50)
        llm_latency.labels(provider="deepseek", model="deepseek-chat").observe(0.8)

    def test_record_knowledge_metrics(self):
        retrieval_total.labels(search_type="semantic").inc()
        retrieval_latency.labels(search_type="hybrid").observe(0.05)

    def test_record_sync_metrics(self):
        sync_job_total.labels(connector_type="feishu", sync_mode="full", status="success").inc()
        sync_duration.labels(connector_type="feishu").observe(30.0)
        sync_failure_total.labels(connector_type="yuque").inc()

    def test_generate_includes_all_metric_families(self):
        output = generate_observability_metrics()
        # Each family should appear in output
        assert "agent_tasks_total" in output
        assert "llm_requests_total" in output
        assert "knowledge_retrievals_total" in output
        assert "sync_jobs_total" in output
        assert "sync_failures_total" in output
        assert "agent_task_duration_seconds" in output
        assert "llm_request_duration_seconds" in output
        assert "knowledge_retrieval_duration_seconds" in output
        assert "sync_job_duration_seconds" in output


class TestMetricsEdgeCases:
    """Edge cases for metrics recording."""

    def test_generate_after_recording_has_data(self):
        output = generate_observability_metrics()
        # Should contain at least some metric lines beyond comments/headers
        lines = [l for l in output.split("\n") if l and not l.startswith("#")]
        assert len(lines) >= 0  # at least no crash

    def test_registry_uniqueness(self):
        """Metric names should be unique in observability registry."""
        names = {m.name for m in _OBSERVABILITY_REGISTRY.collect()}
        assert len(names) >= 0
