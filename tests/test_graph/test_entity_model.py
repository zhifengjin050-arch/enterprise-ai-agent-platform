"""Tests for KnowledgeEntity ORM model.

Tests entity creation, field validation, and type enum.
Note: SQLAlchemy mapped_column(default=...) applies at INSERT time,
so id/entity_type/defaults are None until session.add()+flush().
"""
from __future__ import annotations

import uuid

import pytest

from app.entity.models import EntityType, KnowledgeEntity


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_type_values(self) -> None:
        """EntityType should have all expected values."""
        assert EntityType.SERVICE.value == "service"
        assert EntityType.COMPONENT.value == "component"
        assert EntityType.TECHNOLOGY.value == "technology"
        assert EntityType.TOOL.value == "tool"
        assert EntityType.TEAM.value == "team"
        assert EntityType.PERSON.value == "person"
        assert EntityType.ENVIRONMENT.value == "environment"
        assert EntityType.INCIDENT.value == "incident"
        assert EntityType.SOP.value == "sop"


class TestKnowledgeEntity:
    """Tests for KnowledgeEntity model construction."""

    def test_create_entity_explicit_fields(self) -> None:
        """Entity should store explicitly set fields at construction."""
        entity = KnowledgeEntity(
            name="Redis",
            entity_type=EntityType.TECHNOLOGY,
            description="内存缓存数据库",
        )
        assert entity.name == "Redis"
        assert entity.entity_type == EntityType.TECHNOLOGY
        assert entity.description == "内存缓存数据库"

    def test_entity_string_type(self) -> None:
        """Entity can be created with string type."""
        entity = KnowledgeEntity(name="支付服务", entity_type="service")
        assert entity.entity_type == "service"  # str not converted to enum at construction

    def test_entity_metadata_json(self) -> None:
        """Entity metadata_json should store arbitrary data."""
        entity = KnowledgeEntity(
            name="Redis",
            entity_type="technology",
            metadata_json={"version": "7.0", "cluster": True},
        )
        assert entity.metadata_json["version"] == "7.0"
        assert entity.metadata_json["cluster"] is True

    def test_entity_minimal_construction(self) -> None:
        """Entity can be constructed with only name."""
        entity = KnowledgeEntity(name="Nginx")
        assert entity.name == "Nginx"
        # id is None until persisted (mapped_column default is INSERT-time)
        assert entity.id is None
        # entity_type is None until persisted
        assert entity.entity_type is None