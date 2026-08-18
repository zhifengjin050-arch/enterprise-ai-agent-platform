"""Tests for KnowledgeIndexer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.search.indexer import KnowledgeIndexer


@pytest.mark.asyncio
async def test_indexer_index_document_new() -> None:
    """Test index_document when document has no embedding."""
    indexer = KnowledgeIndexer()

    # Mock embedding
    indexer._embedding = AsyncMock()
    indexer._embedding.embed_text.return_value = [0.1, 0.2, 0.3]

    # Mock store
    indexer._store = AsyncMock()
    indexer._store.count.return_value = 0

    # Mock session + repo
    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc-uuid"
    mock_doc.title = "Test Doc"
    mock_doc.content = "Content here"
    mock_doc.embedding_id = None
    mock_doc.doc_type = MagicMock()
    mock_doc.doc_type.value = "sop"
    mock_doc.tags = []
    mock_doc.source = "local"

    # get_document must be awaitable
    mock_repo.get_document = AsyncMock(return_value=mock_doc)

    with patch("app.search.indexer.get_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        with patch("app.search.indexer.KnowledgeRepository", return_value=mock_repo):
            result = await indexer.index_document("doc-uuid")

    assert result["indexed"] is True
    assert "emb_" in result["embedding_id"]