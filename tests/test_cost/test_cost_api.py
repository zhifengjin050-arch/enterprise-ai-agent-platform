"""Tests for LLM cost admin API."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client() -> AsyncClient:
    """Create test AsyncClient with ASGITransport."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestCostAPI:
    """Test /api/admin/llm/cost endpoint."""

    async def test_get_cost_stats_no_auth_returns_401(self, client: AsyncClient) -> None:
        """Test getting cost stats without auth returns 401."""
        response = await client.get("/api/admin/llm/cost")
        assert response.status_code == 401
