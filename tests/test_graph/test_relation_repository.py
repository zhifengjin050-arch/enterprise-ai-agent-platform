"""Tests for RelationRepository.

Tests CRUD operations for KnowledgeRelation using async SQLAlchemy.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.relation.models import KnowledgeRelation, RelationType
from app.relation.repository import RelationRepository


class TestRelationRepository:
    """Tests for RelationRepository."""

    @pytest.mark.asyncio
    async def test_create_relation(self) -> None:
        """create_relation should persist and return relation."""
        mock_session = AsyncMock()
        repo = RelationRepository(mock_session)
        src_id = uuid.uuid4()
        tgt_id = uuid.uuid4()

        relation = await repo.create_relation(
            source_entity_id=src_id,
            target_entity_id=tgt_id,
            relation_type="depends_on",
            confidence=0.95,
        )
        assert relation.relation_type == RelationType.DEPENDS_ON
        assert relation.confidence == 0.95
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_relations_outgoing(self) -> None:
        """get_relations with direction='outgoing' should filter."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            KnowledgeRelation(
                source_entity_id=uuid.uuid4(),
                target_entity_id=uuid.uuid4(),
                relation_type=RelationType.DEPENDS_ON,
            ),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RelationRepository(mock_session)
        results = await repo.get_relations(
            uuid.uuid4(),
            direction="outgoing",
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_entity_graph(self) -> None:
        """get_entity_graph should return entity and relations."""
        mock_session = AsyncMock()
        # Mock for entity query
        mock_entity_result = MagicMock()
        mock_entity_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_entity_result)

        repo = RelationRepository(mock_session)
        graph = await repo.get_entity_graph(uuid.uuid4())
        assert graph["entity"] is None
        assert graph["relations"] == []

    @pytest.mark.asyncio
    async def test_delete_relation_not_found(self) -> None:
        """delete_relation for non-existent relation returns False."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = RelationRepository(mock_session)
        result = await repo.delete_relation(uuid.uuid4())
        assert result is False

    def test_to_dict(self) -> None:
        """to_dict should serialize relation correctly."""
        src_id = uuid.uuid4()
        tgt_id = uuid.uuid4()
        relation = KnowledgeRelation(
            source_entity_id=src_id,
            target_entity_id=tgt_id,
            relation_type=RelationType.DEPENDS_ON,
            confidence=0.92,
        )
        d = RelationRepository.to_dict(relation)
        assert d["relation_type"] == "depends_on"
        assert d["confidence"] == 0.92
        assert str(src_id) in d["source_entity_id"]
