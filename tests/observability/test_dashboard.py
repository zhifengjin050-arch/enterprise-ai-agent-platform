"""Tests for Dashboard API endpoints (/api/metrics/*)."""

from __future__ import annotations

import pytest


class TestMetricsDashboard:
    """Dashboard API integration tests with auth bypass."""

    @pytest.mark.asyncio
    async def test_metrics_overview_returns_200(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/overview")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_agents_returns_200(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/agents")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_llm_returns_200(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/llm")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_sync_returns_200(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/sync")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_errors_returns_200(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/errors")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_overview_contains_required_fields(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/overview")
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "period_hours" in data
        assert "llm_calls" in data
        assert "agent_executions" in data
        assert "errors_24h" in data

    @pytest.mark.asyncio
    async def test_agents_contains_execution_stats(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/agents")
        data = resp.json()
        assert "total_executions" in data
        assert "failed" in data
        assert "success_rate" in data

    @pytest.mark.asyncio
    async def test_llm_contains_cost_stats(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/llm")
        data = resp.json()
        assert "total_calls" in data
        assert "total_tokens" in data
        assert "total_cost" in data

    @pytest.mark.asyncio
    async def test_errors_contains_error_counts(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/errors")
        data = resp.json()
        assert "total_errors" in data
        assert "per_component" in data

    @pytest.mark.asyncio
    async def test_metrics_unauthorized_without_token(self, api_client):
        """Without auth bypass, should return 401 (no credentials)."""
        resp = await api_client.get("/api/metrics/overview")
        assert resp.status_code == 401


class TestMetricsEdgeCases:
    """Edge cases for dashboard API."""

    @pytest.mark.asyncio
    async def test_overview_db_degraded(self, auth_api_client):
        """Even if DB not fully set up, endpoint should not crash."""
        resp = await auth_api_client.get("/api/metrics/overview")
        data = resp.json()
        # Should gracefully handle missing tables
        assert isinstance(data.get("llm_calls"), int)

    @pytest.mark.asyncio
    async def test_llm_returns_empty_stats_when_no_data(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/llm")
        data = resp.json()
        assert data["total_calls"] >= 0
        assert data["total_tokens"] >= 0

    @pytest.mark.asyncio
    async def test_sync_fallback_when_table_missing(self, auth_api_client):
        resp = await auth_api_client.get("/api/metrics/sync")
        data = resp.json()
        assert "total_syncs" in data
        assert "success_rate" in data
