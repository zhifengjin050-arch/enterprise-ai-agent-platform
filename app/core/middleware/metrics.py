"""Metrics middleware — automatically records HTTP request metrics.

Captures request count, latency, and status for every incoming request
using the existing Prometheus metrics from app/monitor/metrics.py.
"""
from __future__ import annotations

import time
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.monitor.metrics import MetricsCollector


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP request metrics to Prometheus.

    Automatically calls MetricsCollector.record_http_request()
    for every request, populating:
      - http_requests_total{method, endpoint, status}
      - http_request_duration_seconds{method, endpoint}
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start_time = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start_time

        # Summarise the route to avoid high-cardinality path params
        endpoint = request.url.path
        method = request.method

        try:
            MetricsCollector.record_http_request(
                method=method,
                endpoint=endpoint,
                status=response.status_code,
                duration=duration,
            )
        except Exception:
            pass  # never break the request for a metric

        return response
