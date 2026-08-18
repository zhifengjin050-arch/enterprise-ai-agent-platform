"""Tests for the embedding_node in the knowledge pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.workflow.knowledge_pipeline import embedding_node


@pytest.mark.asyncio
async def test_embedding_node_with_api_key() -> None:
    """When API key is set, should call OpenAICompatibleEmbedding."""
    state = {
        "document_id": "doc-001",
        "markdown_content": "# Test\n\nContent to embed.",
        "title": "Test Doc",
    }

    # Patch the SOURCE modules (lazy imports inside function body)
    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.embedding.client.OpenAICompatibleEmbedding") as mock_provider_cls,
    ):
        mock_settings.return_value.llm_api_key = "sk-test"
        mock_settings.return_value.embedding_api_key = None

        mock_provider = AsyncMock()
        mock_provider.embed_text.return_value = [0.1, 0.2, 0.3]
        mock_provider_cls.return_value = mock_provider

        result = await embedding_node(state)

    assert result.get("embedding_id") is not None
    assert "emb_" in result["embedding_id"]
    assert "_dim3" in result["embedding_id"]
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_embedding_node_fallback() -> None:
    """Without API key, should generate a placeholder embedding_id."""
    state = {
        "document_id": "doc-002",
        "markdown_content": "# Test\n\nFallback content.",
        "title": "Fallback Doc",
    }

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.llm_api_key = ""
        mock_settings.return_value.embedding_api_key = ""

        result = await embedding_node(state)

    assert result.get("embedding_id") is not None
    assert result["embedding_id"] == "emb_doc-002"
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_embedding_node_api_error_fallback() -> None:
    """When API call fails, should still produce fallback id with warning."""
    state = {
        "document_id": "doc-003",
        "markdown_content": "# Test\n\nContent.",
        "title": "Error Doc",
    }

    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.embedding.client.OpenAICompatibleEmbedding") as mock_provider_cls,
    ):
        mock_settings.return_value.llm_api_key = "sk-test"
        mock_provider = AsyncMock()
        mock_provider.embed_text.side_effect = RuntimeError("API timeout")
        mock_provider_cls.return_value = mock_provider

        result = await embedding_node(state)

    assert result.get("embedding_id") is not None
    assert "emb_" in result["embedding_id"]
    assert "warning" in (result.get("error") or "").lower()


@pytest.mark.asyncio
async def test_embedding_node_empty_content() -> None:
    """Empty content should return None embedding_id."""
    state = {
        "document_id": "doc-004",
        "markdown_content": "",
        "title": "",
    }

    result = await embedding_node(state)

    assert result.get("embedding_id") is None
    assert "No content" in (result.get("error") or "")