"""Tests for GraphQueryService and GraphTraversal.

Tests entity lookup, neighbor queries, and path finding.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.graph.query import GraphQueryService
from app.graph.traversal import GraphTraversal, find_path_between


class TestGraphQueryService:
    """Tests for GraphQueryService."""

    @pytest.mark.asyncio
    async def test_get_entity_no_session(self) -> None:
        """Without session, get_entity returns None."""
        service = GraphQueryService()
        result = await service.get_entity("Redis")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_entity_found(self) -> None:
        """get_entity should return entity dict when found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_entity = MagicMock()
        mock_entity.name = "Redis"
        mock_entity.entity_type.value = "technology"
        mock_entity.description = "缓存数据库"
        mock_entity.metadata_json = {}
        mock_entity.created_at = None
        mock_entity.updated_at = None
        mock_result.scalars.return_value.all.return_value = [mock_entity]
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = GraphQueryService()
        result = await service.get_entity("Redis", session=mock_session)
        assert result is not None
        assert result["name"] == "Redis"

    @pytest.mark.asyncio
    async def test_get_neighbors_no_session(self) -> None:
        """Without session, get_neighbors returns empty."""
        service = GraphQueryService()
        result = await service.get_neighbors("Redis")
        assert result["entity"] is None
        assert result["neighbors"] == []

    @pytest.mark.asyncio
    async def test_find_path_no_session(self) -> None:
        """Without session, find_path returns not found."""
        service = GraphQueryService()
        result = await service.find_path("Redis", "MySQL")
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_search_entities_no_session(self) -> None:
        """Without session, search_entities returns empty."""
        service = GraphQueryService()
        result = await service.search_entities("Redis")
        assert result == []


class TestGraphTraversal:
    """Tests for GraphTraversal."""

    @pytest.mark.asyncio
    async def test_find_path_no_session(self) -> None:
        """Without session, find_path returns not found."""
        traversal = GraphTraversal()
        result = await traversal.find_path("Redis", "MySQL")
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_find_path_between_no_session(self) -> None:
        """find_path_between without session returns not found."""
        result = await find_path_between("Redis", "MySQL")
        assert result["found"] is False
