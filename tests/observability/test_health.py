"""Tests for Health Check endpoint."""

from __future__ import annotations

import pytest


class TestHealthEndpoint:
    """/api/health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, api_client):
        resp = await api_client.get("/api/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_contains_required_fields(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "service" in data
        assert "components" in data

    @pytest.mark.asyncio
    async def test_health_status_is_valid(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    @pytest.mark.asyncio
    async def test_health_contains_component_details(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        comps = data["components"]
        assert "database" in comps
        # At least database detail present

    @pytest.mark.asyncio
    async def test_health_components_have_valid_states(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        valid_states = {"healthy", "degraded", "unhealthy", "not_configured"}
        for name, state in data["components"].items():
            assert state in valid_states, f"{name}: {state}"

    @pytest.mark.asyncio
    async def test_health_version_matches(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        from app.core.config import get_settings

        assert data["version"] == get_settings().app_version

    @pytest.mark.asyncio
    async def test_health_service_name_present(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        from app.core.config import get_settings

        assert data["service"] == get_settings().service_name


class TestMonitorEndpoint:
    """Monitor /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self, api_client):
        resp = await api_client.get("/metrics")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_content_type(self, api_client):
        resp = await api_client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")
