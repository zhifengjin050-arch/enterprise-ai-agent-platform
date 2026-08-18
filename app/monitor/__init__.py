"""Prometheus monitoring package for enterprise knowledge copilot.

Provides HTTP request metrics, workflow metrics, and LLM metrics.
Exposes /metrics endpoint for Prometheus scraping.
"""
from app.monitor.metrics import MetricsCollector, metrics

__all__ = [
    "MetricsCollector",
    "metrics",
]
