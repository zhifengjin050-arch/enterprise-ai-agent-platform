"""Knowledge Entity ORM model.

Represents a named entity extracted from enterprise documents.
Entities can be services, components, technologies, tools, teams,
persons, environments, incidents, or SOPs.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Enum, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class EntityType(str, enum.Enum):
    """Supported entity types for knowledge graph entities."""

    SERVICE = "service"
    COMPONENT = "component"
    TECHNOLOGY = "technology"
    TOOL = "tool"
    TEAM = "team"
    PERSON = "person"
    ENVIRONMENT = "environment"
    INCIDENT = "incident"
    SOP = "sop"
    # Phase 5 Intelligence Layer extensions
    ORGANIZATION = "organization"
    PROJECT = "project"
    SYSTEM = "system"
    API = "api"


class KnowledgeEntity(Base):
    """A named entity in the enterprise knowledge graph.

    Attributes:
        id: UUID primary key.
        name: Entity name (e.g., "Redis", "订单服务").
        entity_type: Entity type classification.
        description: Optional description of the entity.
        metadata_json: Optional JSON metadata.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "knowledge_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type_enum", native_enum=False),
        nullable=False,
        default=EntityType.COMPONENT,
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
