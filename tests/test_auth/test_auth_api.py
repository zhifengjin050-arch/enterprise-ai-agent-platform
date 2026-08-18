"""Tests for auth API endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def override_dependencies() -> None:
    """Override DB dependency with mock returning None for user queries."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []

    async def _mock_get_db():
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        yield session

    app.dependency_overrides[get_db] = _mock_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncClient:
    """Create test AsyncClient with ASGITransport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAuthAPI:
    """Test /api/auth endpoints."""

    async def test_login_invalid_returns_401(self, client: AsyncClient) -> None:
        """Test login with invalid credentials returns 401."""
        response = await client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_get_me_no_auth_returns_401(self, client: AsyncClient) -> None:
        """Test GET /api/auth/me returns 401 without auth."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token_returns_401(self, client: AsyncClient) -> None:
        """Test GET /api/auth/me with invalid token returns 401."""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_xyz"},
        )
        assert response.status_code == 401