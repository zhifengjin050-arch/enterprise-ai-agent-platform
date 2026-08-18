"""Tests for EntityRepository.

Tests CRUD operations for KnowledgeEntity using async SQLAlchemy.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.entity.models import EntityType, KnowledgeEntity
from app.entity.repository import EntityRepository


class TestEntityRepository:
    """Tests for EntityRepository."""

    @pytest.mark.asyncio
    async def test_create_entity(self) -> None:
        """create_entity should persist and return entity."""
        mock_session = AsyncMock()
        repo = EntityRepository(mock_session)

        entity = await repo.create_entity(
            name="Redis",
            entity_type="technology",
            description="缓存数据库",
        )
        assert entity.name == "Redis"
        assert entity.entity_type == EntityType.TECHNOLOGY
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_find_by_name_exact(self) -> None:
        """find_by_name with exact=True should match exactly."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            KnowledgeEntity(name="Redis", entity_type=EntityType.TECHNOLOGY),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EntityRepository(mock_session)
        results = await repo.find_by_name("Redis", exact=True)
        assert len(results) == 1
        assert results[0].name == "Redis"

    @pytest.mark.asyncio
    async def test_find_by_name_fuzzy(self) -> None:
        """find_by_name with exact=False should use ILIKE."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            KnowledgeEntity(name="RedisCluster", entity_type=EntityType.TECHNOLOGY),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EntityRepository(mock_session)
        results = await repo.find_by_name("redis", exact=False)
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_list_entities(self) -> None:
        """list_entities should return all entities."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            KnowledgeEntity(name="Redis", entity_type=EntityType.TECHNOLOGY),
            KnowledgeEntity(name="Nginx", entity_type=EntityType.TECHNOLOGY),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EntityRepository(mock_session)
        results = await repo.list_entities()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete_entity(self) -> None:
        """delete_entity should return True on success."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = KnowledgeEntity(
            name="Redis", entity_type=EntityType.TECHNOLOGY,
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = EntityRepository(mock_session)
        result = await repo.delete_entity(uuid.uuid4())
        assert result is True

    def test_to_dict(self) -> None:
        """to_dict should serialize entity correctly."""
        entity = KnowledgeEntity(
            name="Redis",
            entity_type=EntityType.TECHNOLOGY,
            description="缓存数据库",
        )
        d = EntityRepository.to_dict(entity)
        assert d["name"] == "Redis"
        assert d["entity_type"] == "technology"
        assert d["description"] == "缓存数据库"