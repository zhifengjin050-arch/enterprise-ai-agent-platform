"""Tests for KnowledgeRelation ORM model.

Tests relation creation, field validation, and type enum.
Note: SQLAlchemy mapped_column(default=...) applies at INSERT time,
so id/relation_type/confidence are None/0.0 until session.add()+flush().
"""
from __future__ import annotations

import uuid

import pytest

from app.entity.models import EntityType
from app.relation.models import KnowledgeRelation, RelationType


class TestRelationType:
    """Tests for RelationType enum."""

    def test_relation_type_values(self) -> None:
        """RelationType should have all expected values."""
        assert RelationType.DEPENDS_ON.value == "depends_on"
        assert RelationType.BELONGS_TO.value == "belongs_to"
        assert RelationType.USES.value == "uses"
        assert RelationType.RELATED_TO.value == "related_to"
        assert RelationType.CAUSED_BY.value == "caused_by"
        assert RelationType.SOLVED_BY.value == "solved_by"
        assert RelationType.OWNED_BY.value == "owned_by"


class TestKnowledgeRelation:
    """Tests for KnowledgeRelation model."""

    def test_create_relation_explicit(self) -> None:
        """Relation should store explicitly set fields at construction."""
        src_id = uuid.uuid4()
        tgt_id = uuid.uuid4()
        relation = KnowledgeRelation(
            source_entity_id=src_id,
            target_entity_id=tgt_id,
            relation_type=RelationType.DEPENDS_ON,
            confidence=0.92,
            source_document_id="doc-abc",
        )
        assert relation.source_entity_id == src_id
        assert relation.target_entity_id == tgt_id
        assert relation.relation_type == RelationType.DEPENDS_ON
        assert relation.confidence == 0.92
        assert relation.source_document_id == "doc-abc"

    def test_relation_minimal_construction(self) -> None:
        """Minimal construction should have None for server-side defaults."""
        src_id = uuid.uuid4()
        tgt_id = uuid.uuid4()
        relation = KnowledgeRelation(
            source_entity_id=src_id,
            target_entity_id=tgt_id,
        )
        # Server-side defaults (id, relation_type, confidence) are None/0.0 at construction
        assert relation.source_entity_id == src_id
        assert relation.target_entity_id == tgt_id
        # id is None until flush; relation_type is None; confidence is None
        assert relation.id is None
        assert relation.relation_type is None
        assert relation.confidence is None