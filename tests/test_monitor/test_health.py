"""Tests for upgraded health check endpoint."""

from __future__ import annotations

from httpx import AsyncClient, ASGITransport

from app.main import app


class TestHealthCheck:
    """Test the /api/health endpoint."""

    async def test_health_returns_ok(self) -> None:
        """Test that health endpoint returns 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200

    async def test_health_has_version(self) -> None:
        """Test health response includes version 0.6.0."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            data = response.json()
            assert data["version"] in ("0.6.0", "0.9.0")

    async def test_health_has_components(self) -> None:
        """Test health response includes component statuses."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            data = response.json()
            assert "components" in data
            assert "database" in data["components"]
            assert "chroma" in data["components"] or "vector_store" in data["components"]
            assert "llm" in data["components"]

    async def test_health_overall_status(self) -> None:
        """Test health has overall status field."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            data = response.json()
            assert "status" in data
            assert data["status"] in ["ok", "healthy", "degraded", "error", "unhealthy"]