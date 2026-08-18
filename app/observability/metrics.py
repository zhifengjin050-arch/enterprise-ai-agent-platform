"""Enhanced Prometheus Metrics — extended agent, llm, retrieval, sync metrics.

Uses a separate CollectorRegistry to avoid conflicting with
existing metrics registered by app/monitor/metrics.py.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# Use a dedicated registry so Phase 8 metrics coexist with Phase 2 monitor metrics
_OBSERVABILITY_REGISTRY = CollectorRegistry()

# ── Agent ──
agent_task_total = Counter(
    "agent_tasks_total", "Agent task executions", ["agent_type", "status"],
    registry=_OBSERVABILITY_REGISTRY,
)
agent_task_latency = Histogram(
    "agent_task_duration_seconds", "Agent task latency",
    ["agent_type"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=_OBSERVABILITY_REGISTRY,
)
agent_failure_total = Counter(
    "agent_failures_total", "Agent task failures", ["agent_type", "error_code"],
    registry=_OBSERVABILITY_REGISTRY,
)

# ── LLM ──
llm_request_total = Counter(
    "llm_requests_total", "LLM API calls", ["provider", "model", "request_type"],
    registry=_OBSERVABILITY_REGISTRY,
)
llm_latency = Histogram(
    "llm_request_duration_seconds", "LLM call latency",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=_OBSERVABILITY_REGISTRY,
)
llm_tokens_input = Counter(
    "llm_tokens_input_total", "Input tokens", ["provider", "model"],
    registry=_OBSERVABILITY_REGISTRY,
)
llm_tokens_output = Counter(
    "llm_tokens_output_total", "Output tokens", ["provider", "model"],
    registry=_OBSERVABILITY_REGISTRY,
)

# ── Knowledge ──
retrieval_total = Counter(
    "knowledge_retrievals_total", "Knowledge retrieval requests", ["search_type"],
    registry=_OBSERVABILITY_REGISTRY,
)
retrieval_latency = Histogram(
    "knowledge_retrieval_duration_seconds", "Retrieval latency",
    ["search_type"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
    registry=_OBSERVABILITY_REGISTRY,
)

# ── Sync ──
sync_job_total = Counter(
    "sync_jobs_total", "Sync job executions", ["connector_type", "sync_mode", "status"],
    registry=_OBSERVABILITY_REGISTRY,
)
sync_duration = Histogram(
    "sync_job_duration_seconds", "Sync job duration",
    ["connector_type"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=_OBSERVABILITY_REGISTRY,
)
sync_failure_total = Counter(
    "sync_failures_total", "Sync job failures", ["connector_type"],
    registry=_OBSERVABILITY_REGISTRY,
)

# ── System ──
active_agents = Gauge(
    "active_agents", "Currently running agents",
    registry=_OBSERVABILITY_REGISTRY,
)
active_sync_jobs = Gauge(
    "active_sync_jobs", "Currently running sync jobs",
    registry=_OBSERVABILITY_REGISTRY,
)
uptime_seconds = Gauge(
    "uptime_seconds", "Service uptime in seconds",
    registry=_OBSERVABILITY_REGISTRY,
)


def generate_observability_metrics() -> str:
    """Generate Prometheus-formatted metrics for Phase 8 observability."""
    return generate_latest(_OBSERVABILITY_REGISTRY).decode("utf-8")
