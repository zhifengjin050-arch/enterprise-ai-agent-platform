"""Tests for ChunkEmbeddingService."""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock

import pytest

from app.knowledge.chunking import Chunk
from app.knowledge.embedding import ChunkEmbeddingService


class FakeProvider:
    """Minimal EmbeddingProvider double."""

    async def embed_text(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3]

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def get_dimension(self) -> int:
        return 3

    async def close(self) -> None:
        pass


class TestChunkEmbeddingService:
    async def test_embed_chunks(self) -> None:
        service = ChunkEmbeddingService(provider=FakeProvider())  # type: ignore[arg-type]
        chunks = [
            Chunk(content="hello", document_id="d"),
            Chunk(content="world", document_id="d"),
        ]
        vectors = await service.embed_chunks(chunks)
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]

    async def test_embed_empty(self) -> None:
        service = ChunkEmbeddingService(provider=FakeProvider())  # type: ignore[arg-type]
        assert await service.embed_chunks([]) == []

    async def test_embed_query(self) -> None:
        service = ChunkEmbeddingService(provider=FakeProvider())  # type: ignore[arg-type]
        vec = await service.embed_query("test query")
        assert vec == [0.1, 0.2, 0.3]