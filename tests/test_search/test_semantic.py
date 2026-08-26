"""Tests for SemanticSearch engine with mocked embedding and vector store."""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock

import pytest

from app.search.semantic import SemanticResult, SemanticSearch
from app.vectorstore.base import VectorSearchResult


@pytest.fixture
def mock_embedding() -> AsyncMock:
    m = AsyncMock()
    m.embed_text.return_value = [0.1, 0.2, 0.3]
    return m


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    m = AsyncMock()
    m.query.return_value = [
        VectorSearchResult(
            id="emb_d1",
            document_id="doc-uuid-1",
            score=0.92,
            metadata={"title": "SOP Guide", "doc_type": "sop"},
            content="# SOP Guide\nStep 1...",
        ),
        VectorSearchResult(
            id="emb_d2",
            document_id="doc-uuid-2",
            score=0.85,
            metadata={"title": "Incident Report", "doc_type": "incident"},
            content="## Incident\nWhat happened...",
        ),
    ]
    return m


@pytest.mark.asyncio
async def test_semantic_search_returns_results(
    mock_embedding: AsyncMock,
    mock_vector_store: AsyncMock,
) -> None:
    engine = SemanticSearch(
        embedding_provider=mock_embedding,  # type: ignore[arg-type]
        vector_store=mock_vector_store,  # type: ignore[arg-type]
    )
    results: List[SemanticResult] = await engine.search(query="how to deploy", top_k=2)

    assert len(results) == 2
    assert results[0].id == "doc-uuid-1"
    assert results[0].title == "SOP Guide"
    assert results[0].score == 0.92
    assert results[1].id == "doc-uuid-2"


@pytest.mark.asyncio
async def test_semantic_search_with_filters(
    mock_embedding: AsyncMock,
    mock_vector_store: AsyncMock,
) -> None:
    engine = SemanticSearch(
        embedding_provider=mock_embedding,  # type: ignore[arg-type]
        vector_store=mock_vector_store,  # type: ignore[arg-type]
    )
    await engine.search(query="deploy", top_k=5, filters={"doc_type": "sop"})

    mock_embedding.embed_text.assert_awaited_once_with("deploy")
    mock_vector_store.query.assert_awaited_once()
    assert mock_vector_store.query.call_args.kwargs["metadata_filter"] == {"doc_type": "sop"}


@pytest.mark.asyncio
async def test_semantic_search_by_vector() -> None:
    """search_by_vector should return results using pre-computed embedding."""
    mock_store = AsyncMock()
    mock_store.query.return_value = [
        VectorSearchResult(
            id="emb_d1",
            document_id="doc-uuid-1",
            score=0.92,
            metadata={"title": "Test Doc"},
            content="content",
        ),
    ]
    engine = SemanticSearch(vector_store=mock_store)  # type: ignore[arg-type]
    results = await engine.search_by_vector(
        embedding=[0.1, 0.2, 0.3],
        top_k=1,
    )
    assert len(results) == 1
    assert results[0].id == "doc-uuid-1"
    assert results[0].score == 0.92


@pytest.mark.asyncio
async def test_semantic_search_empty(mock_embedding: AsyncMock) -> None:
    empty_store = AsyncMock()
    empty_store.query.return_value = []
    engine = SemanticSearch(
        embedding_provider=mock_embedding,  # type: ignore[arg-type]
        vector_store=empty_store,  # type: ignore[arg-type]
    )
    results = await engine.search(query="nothing", top_k=5)
    assert results == []
