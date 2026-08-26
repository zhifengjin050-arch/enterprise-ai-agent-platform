"""Tests for MetricsMiddleware auto-recording."""

from __future__ import annotations

import pytest

from app.core.middleware.metrics import MetricsMiddleware


class TestMetricsMiddleware:
    """MetricsMiddleware structure and integration tests."""

    def test_middleware_is_class(self):
        assert isinstance(MetricsMiddleware, type)

    def test_middleware_has_dispatch_method(self):
        assert hasattr(MetricsMiddleware, "dispatch")

    @pytest.mark.asyncio
    async def test_middleware_records_http_total(self, api_client):
        """Hitting a fresh route should increment http_requests_total."""
        from app.monitor.metrics import http_request_count

        # Use a unique path to get a fresh label combo
        samples = http_request_count.collect()[0].samples
        path_counts = {}
        for s in samples:
            if s.name == "http_requests_total":
                key = (s.labels["method"], s.labels["endpoint"])
                path_counts[key] = s.value

        await api_client.get("/api/health")

        samples_after = http_request_count.collect()[0].samples
        for s in samples_after:
            if s.name == "http_requests_total":
                key = (s.labels["method"], s.labels["endpoint"])
                if key == ("GET", "/api/health"):
                    prev = path_counts.get(key, 0.0)
                    assert s.value == prev + 1.0, f"Expected increment for {key}"
                    return

        # If /api/health label not found, that's also ok — middleware ran
        raise AssertionError("/api/health not found in metrics")

    @pytest.mark.asyncio
    async def test_middleware_does_not_break_on_error(self, api_client):
        """Even with a 404, middleware should not raise."""
        resp = await api_client.get("/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_middleware_records_latency(self, api_client):
        """Histogram should record observations after a request."""
        from app.monitor.metrics import http_request_duration

        await api_client.get("/nonexistent")
        # After any request, at least one bucket should have an observation
        samples = http_request_duration.collect()[0].samples
        count_samples = [s for s in samples if s.name.endswith("_count")]
        assert len(count_samples) > 0
