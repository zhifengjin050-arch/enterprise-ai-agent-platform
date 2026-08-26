"""Prometheus metrics collector.

Provides counters, histograms, and gauges for:
- HTTP requests (count, latency)
- Workflow executions (count, failures)
- LLM calls (count, tokens)
- Embedding calls (count)
- Search latency

Uses the prometheus_client library. All metrics are process-local
and exposed via the /metrics endpoint.
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── HTTP Metrics ──
http_request_count = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Workflow Metrics ──
workflow_execution_count = Counter(
    "workflow_executions_total",
    "Total workflow executions",
    ["workflow_type"],
)

workflow_failure_count = Counter(
    "workflow_failures_total",
    "Total workflow failures",
    ["workflow_type"],
)

# ── LLM Metrics ──
llm_call_count = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["provider", "model", "request_type"],
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "type"],  # type: prompt | completion
)

# ── Embedding Metrics ──
embedding_call_count = Counter(
    "embedding_calls_total",
    "Total embedding API calls",
    ["provider"],
)

# ── Search Metrics ──
search_duration = Histogram(
    "search_duration_seconds",
    "Search query latency in seconds",
    ["search_type"],  # semantic | fulltext | hybrid
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ── Resource Metrics ──
active_workflows = Gauge(
    "active_workflows",
    "Number of currently active workflows",
)


class MetricsCollector:
    """Collect and expose Prometheus metrics.

    Static methods for recording common operations.
    """

    @staticmethod
    def record_http_request(
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """Record an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: URL path.
            status: HTTP status code.
            duration: Request duration in seconds.
        """
        http_request_count.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def record_workflow_execution(workflow_type: str = "knowledge") -> None:
        """Record a workflow execution.

        Args:
            workflow_type: Type of workflow.
        """
        workflow_execution_count.labels(workflow_type=workflow_type).inc()

    @staticmethod
    def record_workflow_failure(workflow_type: str = "knowledge") -> None:
        """Record a workflow failure.

        Args:
            workflow_type: Type of workflow.
        """
        workflow_failure_count.labels(workflow_type=workflow_type).inc()

    @staticmethod
    def record_llm_call(
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        request_type: str = "other",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record an LLM API call.

        Args:
            provider: LLM provider name.
            model: Model identifier.
            request_type: Request category.
            prompt_tokens: Input token count.
            completion_tokens: Output token count.
        """
        llm_call_count.labels(provider=provider, model=model, request_type=request_type).inc()

        if prompt_tokens > 0:
            llm_tokens_total.labels(provider=provider, model=model, type="prompt").inc(
                prompt_tokens
            )

        if completion_tokens > 0:
            llm_tokens_total.labels(provider=provider, model=model, type="completion").inc(
                completion_tokens
            )

    @staticmethod
    def record_embedding_call(provider: str = "openai") -> None:
        """Record an embedding API call.

        Args:
            provider: Embedding provider name.
        """
        embedding_call_count.labels(provider=provider).inc()

    @staticmethod
    def record_search_duration(
        search_type: str = "hybrid",
        duration: float = 0.0,
    ) -> None:
        """Record search query latency.

        Args:
            search_type: Type of search (semantic/fulltext/hybrid).
            duration: Duration in seconds.
        """
        search_duration.labels(search_type=search_type).observe(duration)

    @staticmethod
    def set_active_workflows(count: int) -> None:
        """Set the active workflow gauge.

        Args:
            count: Number of active workflows.
        """
        active_workflows.set(count)

    @staticmethod
    def generate_metrics() -> str:
        """Generate Prometheus-formatted metrics.

        Returns:
            Metrics text for /metrics endpoint.
        """
        return generate_latest(REGISTRY).decode("utf-8")


# Module-level singleton
metrics = MetricsCollector()
