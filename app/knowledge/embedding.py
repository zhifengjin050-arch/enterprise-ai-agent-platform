"""Chunk embedding service — wraps app.embedding for the Intelligence Layer.

Provides batch embedding of document chunks and optional persistence of
embedding_id back onto DocumentChunk rows.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from app.embedding.base import EmbeddingProvider
from app.knowledge.chunking import Chunk

logger = logging.getLogger(__name__)


class ChunkEmbeddingService:
    """Embed document chunks using the platform EmbeddingProvider.

    Args:
        provider: Optional EmbeddingProvider override (for tests).
    """

    def __init__(self, provider: Optional[EmbeddingProvider] = None) -> None:
        self._provider = provider

    async def _get_provider(self) -> EmbeddingProvider:
        if self._provider is not None:
            return self._provider
        from app.embedding.client import OpenAICompatibleEmbedding

        return OpenAICompatibleEmbedding()

    async def embed_chunks(
        self, chunks: Sequence[Chunk]
    ) -> List[List[float]]:
        """Generate embedding vectors for a list of chunks.

        Args:
            chunks: Chunks to embed (uses chunk.content).

        Returns:
            List of embedding vectors aligned with input chunks.
        """
        if not chunks:
            return []

        texts = [c.content for c in chunks]
        provider = await self._get_provider()
        try:
            vectors = await provider.embed_documents(texts)
            logger.info("Embedded %d chunks", len(vectors))
            return vectors
        finally:
            # Only close if we created the provider ourselves
            if self._provider is None:
                await provider.close()

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single search query.

        Args:
            query: Query text.

        Returns:
            Embedding vector.
        """
        provider = await self._get_provider()
        try:
            return await provider.embed_text(query)
        finally:
            if self._provider is None:
                await provider.close()


# Convenience alias matching Phase 5 naming
KnowledgeEmbedding = ChunkEmbeddingService
