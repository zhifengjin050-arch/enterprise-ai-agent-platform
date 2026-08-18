"""Knowledge Relation ORM model.

Represents a typed, directed relation between two KnowledgeEntities
in the enterprise knowledge graph.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class RelationType(str, enum.Enum):
    """Supported relation types for knowledge graph edges."""

    DEPENDS_ON = "depends_on"
    BELONGS_TO = "belongs_to"
    USES = "uses"
    RELATED_TO = "related_to"
    CAUSED_BY = "caused_by"
    SOLVED_BY = "solved_by"
    OWNED_BY = "owned_by"


class KnowledgeRelation(Base):
    """A directed typed relation between two knowledge entities.

    Attributes:
        id: UUID primary key.
        source_entity_id: Source entity UUID (FK -> knowledge_entities).
        target_entity_id: Target entity UUID (FK -> knowledge_entities).
        relation_type: Type of relation.
        confidence: Confidence score (0.0 to 1.0).
        source_document_id: Optional originating document UUID.
        metadata_json: Optional JSON metadata.
        created_at: Creation timestamp.
    """

    __tablename__ = "knowledge_relations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType, name="relation_type_enum", native_enum=False),
        nullable=False,
        default=RelationType.RELATED_TO,
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    source_document_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
