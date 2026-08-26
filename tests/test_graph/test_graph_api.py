"""Tests for Graph API endpoints.

Tests GET /api/graph/entity/{name}, /neighbors, /path, /search.
Mocks DB session to avoid real database access.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_mock_result(scalar_result=None):
    """Create a mock result for SQLAlchemy execute()."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = scalar_result or []
    scalars.first.return_value = (scalar_result or [None])[0]
    # scalar_one_or_none
    sr = scalar_result or []
    result.scalar_one_or_none.return_value = sr[0] if sr else None
    result.scalars.return_value = scalars
    return result


def _make_mock_session(entity_list=None):
    """Create a properly configured mock session.

    Returns entity_list for the first execute call, then empty results
    for subsequent calls to avoid cascading mock failures.
    """
    first_result = _make_mock_result(entity_list)
    empty_result = _make_mock_result([])

    class MockSession:
        """A mock that mimics AsyncSession for test purposes."""

        def __init__(self):
            self._call_count = 0

        async def execute(self, stmt):
            self._call_count += 1
            if self._call_count == 1:
                return first_result
            return empty_result

        async def flush(self):
            pass

        async def refresh(self, instance):
            pass

        def add(self, instance):
            pass

        async def delete(self, instance):
            pass

        async def commit(self):
            pass

        async def rollback(self):
            pass

        async def close(self):
            pass

    return MockSession()


def _make_mock_factory(entity_list=None):
    """Create a mock session factory."""
    mock_session = _make_mock_session(entity_list)

    class MockFactory:
        """A mock that mimics async_sessionmaker for test purposes."""

        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

        def __call__(self):
            return self

    return MockFactory()


def _make_mock_entity(name="Redis", entity_type="technology", description="缓存数据库"):
    """Create a mock entity object with the required attributes."""
    mock = MagicMock()
    mock.name = name
    mock.description = description
    mock.metadata_json = {}
    mock.created_at = None
    mock.updated_at = None
    mock.id = "00000000-0000-0000-0000-000000000001"
    mock.entity_type = MagicMock()
    mock.entity_type.value = entity_type
    return mock


class TestGraphEntityAPI:
    """Tests for GET /api/graph/entity/{name}."""

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self) -> None:
        """Non-existent entity should return 404."""
        mock_factory = _make_mock_factory(entity_list=[])

        with patch("app.api.graph.get_session_factory", return_value=mock_factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/graph/entity/NonExistentXYZ")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_entity_found(self) -> None:
        """Existing entity should return entity info."""
        mock_entity = _make_mock_entity(name="Redis", entity_type="technology")
        # Set up: first call (find_by_name) returns entity,
        # all subsequent calls return empty (relations = no need to parse)
        mock_factory = _make_mock_factory(entity_list=[mock_entity])

        with patch("app.api.graph.get_session_factory", return_value=mock_factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/graph/entity/Redis")
        assert response.status_code == 200
        data = response.json()
        # Entity should be returned; relations may be empty
        assert "name" in data

    @pytest.mark.asyncio
    async def test_get_neighbors_not_found(self) -> None:
        """Non-existent entity should return 404."""
        mock_factory = _make_mock_factory(entity_list=[])

        with patch("app.api.graph.get_session_factory", return_value=mock_factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/graph/entity/NonExistentXYZ/neighbors")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_find_path_missing_params(self) -> None:
        """find_path without required params should return 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/graph/path")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_find_path_with_params(self) -> None:
        """find_path with params should return 200."""
        mock_factory = _make_mock_factory()

        with patch("app.api.graph.get_session_factory", return_value=mock_factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/graph/path",
                    params={"source": "Redis", "target": "MySQL"},
                )
        assert response.status_code == 200
        data = response.json()
        assert "found" in data

    @pytest.mark.asyncio
    async def test_search_entities(self) -> None:
        """search_entities should return list."""
        mock_factory = _make_mock_factory()

        with patch("app.api.graph.get_session_factory", return_value=mock_factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/graph/search",
                    params={"q": "nginx"},
                )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
