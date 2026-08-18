"""Tests for the store_node in the knowledge pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflow.knowledge_pipeline import store_node


@pytest.mark.asyncio
async def test_store_node_success() -> None:
    """store_node should persist document via KnowledgeRepository."""
    state = {
        "document_id": "doc-001",
        "markdown_content": "# Stored Doc\n\nContent here.",
        "title": "Stored Doc",
        "doc_type": "sop",
        "tags": ["k8s", "docker"],
        "embedding_id": "emb_doc-001_dim3",
        "quality_score": 0.8,
        "metadata": {"author": "test"},
    }

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "stored-uuid-12345"
    mock_repo.create_document = AsyncMock(return_value=mock_doc)

    # Patch SOURCE modules (lazy imports inside function body)
    with (
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository", return_value=mock_repo),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        result = await store_node(state)

    assert result.get("stored") is True
    assert result.get("document_id") == "stored-uuid-12345"
    assert result.get("error") is None

    mock_repo.create_document.assert_awaited_once()
    call_kwargs = mock_repo.create_document.call_args[1]
    assert call_kwargs["title"] == "Stored Doc"
    assert call_kwargs["doc_type"] == "sop"
    assert call_kwargs["embedding_id"] == "emb_doc-001_dim3"
    assert call_kwargs["tag_names"] == ["k8s", "docker"]


@pytest.mark.asyncio
async def test_store_node_failure() -> None:
    """When repository raises, store_node should return stored=False."""
    state = {
        "document_id": "doc-002",
        "markdown_content": "# Content",
        "title": "Failing Doc",
    }

    with (
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.create_document = AsyncMock(side_effect=RuntimeError("DB connection lost"))
        mock_repo_cls.return_value = mock_repo

        mock_session = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        result = await store_node(state)

    assert result.get("stored") is False
    assert result.get("error") is not None
    assert "DB connection lost" in result["error"]


@pytest.mark.asyncio
async def test_store_node_minimal_state() -> None:
    """Should handle state with only minimal required fields."""
    state: dict = {}

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "minimal-uuid"
    mock_repo.create_document = AsyncMock(return_value=mock_doc)

    with (
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository", return_value=mock_repo),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        result = await store_node(state)

    assert result.get("stored") is True
    assert mock_repo.create_document.call_args[1]["title"] == "Untitled"