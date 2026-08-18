"""Document chunk ORM model for the Knowledge Intelligence Layer.

Stores structured chunks produced by SmartChunker for chunk-level
embedding, hybrid retrieval, and reranking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class DocumentChunk(Base):
    """A single content chunk derived from a knowledge document.

    Attributes:
        id: UUID primary key.
        document_id: FK to knowledge_documents.id.
        chunk_index: Zero-based order within the document.
        content: Chunk text content.
        heading: Nearest Markdown heading (if any).
        token_count: Estimated token count.
        embedding_id: Optional vector store ID for this chunk.
        metadata_json: Extra metadata (code_block, table, etc.).
        created_at: Creation timestamp.
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True,
        comment="FK to knowledge_documents.id",
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "heading": self.heading,
            "token_count": self.token_count,
            "embedding_id": self.embedding_id,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
