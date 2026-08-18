"""Monitoring API endpoints.

Provides /metrics endpoint in Prometheus format.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.monitor.metrics import metrics

router = APIRouter(tags=["Monitor"])

_CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics text.
    """
    return Response(
        content=metrics.generate_metrics(),
        media_type=_CONTENT_TYPE_LATEST,
    )
