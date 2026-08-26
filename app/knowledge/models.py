"""
Knowledge ORM models.

Enterprise knowledge asset entities: Document, Category, Tag, and
many-to-many association tables. Uses SQLAlchemy 2.0 mapped columns
and shared DeclarativeBase from app.db.base.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class DocType(str, enum.Enum):
    """Knowledge document type enumeration."""

    SOP = "SOP"
    INCIDENT = "INCIDENT"
    BEST_PRACTICE = "BEST_PRACTICE"
    ARCHITECTURE = "ARCHITECTURE"
    CONFIGURATION = "CONFIGURATION"
    OTHER = "OTHER"


class DocumentStatus(str, enum.Enum):
    """Knowledge document lifecycle status."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DocumentSource(str, enum.Enum):
    """Knowledge document origin."""

    LOCAL = "local"
    FEISHU = "feishu"
    YUQUE = "yuque"
    UPLOAD = "upload"
    API = "api"
    MANUAL = "manual"


# Association tables
document_tags = Table(
    "document_tags",
    Base.metadata,
    Column(
        "document_id", Uuid(as_uuid=True), ForeignKey("knowledge_documents.id"), primary_key=True
    ),
    Column("tag_id", Uuid(as_uuid=True), ForeignKey("tags.id"), primary_key=True),
)

document_categories = Table(
    "document_categories",
    Base.metadata,
    Column(
        "document_id", Uuid(as_uuid=True), ForeignKey("knowledge_documents.id"), primary_key=True
    ),
    Column("category_id", Uuid(as_uuid=True), ForeignKey("categories.id"), primary_key=True),
)

# Backward-compatible aliases for modules still importing old names
document_tag_table = document_tags
document_category_table = document_categories


class KnowledgeDocument(Base):
    """Core enterprise knowledge document."""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="markdown")
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType, name="doc_type_enum", native_enum=False),
        nullable=False,
        default=DocType.OTHER,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum", native_enum=False),
        nullable=False,
        default=DocumentStatus.DRAFT,
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentSource.LOCAL.value
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
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
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    primary_category: Mapped[Optional["KnowledgeCategory"]] = relationship(
        "KnowledgeCategory",
        foreign_keys=[category_id],
        back_populates="primary_documents",
    )
    categories: Mapped[List["KnowledgeCategory"]] = relationship(
        secondary=document_categories,
        back_populates="documents",
    )
    tags: Mapped[List["KnowledgeTag"]] = relationship(
        secondary=document_tags,
        back_populates="documents",
    )

    @property
    def is_active(self) -> bool:
        """Compatibility helper: active means not archived."""
        return self.status != DocumentStatus.ARCHIVED

    @property
    def summary(self) -> Optional[str]:
        """Compatibility helper for searcher (first 200 chars)."""
        if not self.content:
            return None
        return self.content[:200]


class KnowledgeCategory(Base):
    """Tree-structured knowledge category."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    parent: Mapped[Optional["KnowledgeCategory"]] = relationship(
        "KnowledgeCategory",
        remote_side="KnowledgeCategory.id",
        back_populates="children",
    )
    children: Mapped[List["KnowledgeCategory"]] = relationship(
        "KnowledgeCategory",
        back_populates="parent",
    )
    primary_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        foreign_keys="KnowledgeDocument.category_id",
        back_populates="primary_category",
    )
    documents: Mapped[List["KnowledgeDocument"]] = relationship(
        secondary=document_categories,
        back_populates="categories",
    )


class KnowledgeTag(Base):
    """Knowledge tag for multi-label classification."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    documents: Mapped[List["KnowledgeDocument"]] = relationship(
        secondary=document_tags,
        back_populates="tags",
    )
