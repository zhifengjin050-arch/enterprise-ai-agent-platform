"""Semantic search engine.

Provides vector similarity search over knowledge documents using
ChromaDB. Converts text queries to embeddings, then performs
similarity search with optional metadata filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.embedding.client import OpenAICompatibleEmbedding
from app.vectorstore.base import VectorSearchResult
from app.vectorstore.chroma_store import ChromaStore


@dataclass
class SemanticResult:
    """A single semantic search result."""

    id: str
    title: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticSearch:
    """Semantic search engine using embedding + vector similarity.

    Converts query text to an embedding vector via EmbeddingProvider,
    then queries ChromaDB for nearest neighbors with optional metadata
    filtering.
    """

    def __init__(
        self,
        embedding_provider: Optional[OpenAICompatibleEmbedding] = None,
        vector_store: Optional[ChromaStore] = None,
    ) -> None:
        settings = get_settings()
        self._embedding = embedding_provider or OpenAICompatibleEmbedding()
        self._store = vector_store or ChromaStore()

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SemanticResult]:
        """Execute a semantic search using vector similarity.

        Args:
            query: Natural language query string.
            top_k: Maximum number of results.
            filters: Optional metadata filters (e.g. {"doc_type": "sop"}).

        Returns:
            List of SemanticResult ordered by similarity score.
        """
        # 1. Convert query to embedding
        query_vector = await self._embedding.embed_text(query)

        # 2. Search ChromaDB
        raw_results: List[VectorSearchResult] = await self._store.query(
            query_embedding=query_vector,
            top_k=top_k,
            metadata_filter=filters,
        )

        # 3. Map to SemanticResult
        output: List[SemanticResult] = []
        for r in raw_results:
            meta = r.metadata or {}
            output.append(
                SemanticResult(
                    id=r.document_id,
                    title=meta.get("title", ""),
                    content=r.content or "",
                    score=r.score,
                    metadata=meta,
                )
            )
        return output

    async def search_by_vector(
        self,
        embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SemanticResult]:
        """Search using a pre-computed embedding vector.

        Args:
            embedding: Pre-computed query embedding.
            top_k: Maximum number of results.
            filters: Optional metadata filters.

        Returns:
            List of SemanticResult ordered by similarity score.
        """
        raw_results = await self._store.query(
            query_embedding=embedding,
            top_k=top_k,
            metadata_filter=filters,
        )
        output: List[SemanticResult] = []
        for r in raw_results:
            meta = r.metadata or {}
            output.append(
                SemanticResult(
                    id=r.document_id,
                    title=meta.get("title", ""),
                    content=r.content or "",
                    score=r.score,
                    metadata=meta,
                )
            )
        return output

    async def close(self) -> None:
        """Release underlying HTTP client resources."""
        await self._embedding.close()


# Module-level convenience instance
_semantic_search: Optional[SemanticSearch] = None


def get_semantic_search() -> SemanticSearch:
    """Return a singleton SemanticSearch instance."""
    global _semantic_search
    if _semantic_search is None:
        _semantic_search = SemanticSearch()
    return _semantic_search
