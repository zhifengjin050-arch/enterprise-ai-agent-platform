"""Tests for Sync Engine API endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestSyncAPI:
    """Tests for /api/sync endpoints (auth-gated)."""

    async def test_list_jobs_no_auth(self, api_client: AsyncClient) -> None:
        """Test GET /api/sync/jobs returns 401 without auth."""
        resp = await api_client.get("/api/sync/jobs")
        assert resp.status_code == 401

    async def test_get_job_no_auth(self, api_client: AsyncClient) -> None:
        """Test GET /api/sync/jobs/{id} returns 401 without auth."""
        resp = await api_client.get("/api/sync/jobs/nonexistent")
        assert resp.status_code == 401

    async def test_get_events_no_auth(self, api_client: AsyncClient) -> None:
        """Test GET /api/sync/jobs/{id}/events returns 401 without auth."""
        resp = await api_client.get("/api/sync/jobs/nonexistent/events")
        assert resp.status_code == 401

    async def test_connector_sync_no_auth(self, api_client: AsyncClient) -> None:
        """Test POST /api/connectors/{id}/sync returns 401 without auth."""
        resp = await api_client.post("/api/connectors/nonexistent/sync")
        assert resp.status_code == 401

    async def test_sync_routes_registered(self, api_client: AsyncClient) -> None:
        """Test sync routes exist (OpenAPI includes them)."""
        resp = await api_client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})
        assert "/api/sync/jobs" in paths
        assert "/api/sync/jobs/{job_id}" in paths
        assert "/api/sync/jobs/{job_id}/events" in paths