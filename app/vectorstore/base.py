"""Vector store abstraction.

Defines the interface for vector storage backends used in the
knowledge platform's semantic search pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VectorSearchResult:
    """A single result from a vector similarity search."""

    id: str
    document_id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: Optional[str] = None


class VectorStore(ABC):
    """Abstract interface for vector storage backends.

    Implementations wrap ChromaDB, pgvector, or other vector databases
    to provide document-level semantic search capabilities.
    """

    @abstractmethod
    async def add(
        self,
        document_id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Add a document vector to the store.

        Args:
            document_id: Unique identifier for the document.
            embedding: Float vector (e.g. 1536 dimensions).
            metadata: Optional key-value metadata dict.
            content: Optional text content (Markdown summary).
        """
        ...

    @abstractmethod
    async def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Add multiple document vectors in one batch call.

        Args:
            ids: Document IDs.
            embeddings: Vectors for each document.
            metadatas: Per-document metadata (same length as ids).
            contents: Per-document content strings (same length as ids).
        """
        ...

    @abstractmethod
    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search for similar documents by embedding.

        Args:
            query_embedding: Query vector.
            top_k: Max results.
            metadata_filter: Optional equality filters applied before search.

        Returns:
            List of VectorSearchResult ordered by similarity (closest first).
        """
        ...

    @abstractmethod
    async def delete(self, document_id: str) -> None:
        """Remove a single document from the store.

        Args:
            document_id: Document identifier to remove.
        """
        ...

    @abstractmethod
    async def delete_batch(self, ids: List[str]) -> None:
        """Remove multiple documents from the store."""
        ...

    @abstractmethod
    async def update(
        self,
        document_id: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Update an existing document's vector / metadata / content.

        Args:
            document_id: Document identifier to update.
            embedding: Optional new embedding vector.
            metadata: Optional new metadata.
            content: Optional new content text.
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of documents in the store."""
        ...
