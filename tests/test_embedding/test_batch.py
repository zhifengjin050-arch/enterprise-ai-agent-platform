"""Tests for batch embedding with chunking."""

from __future__ import annotations

from typing import Any, Callable, List
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.embedding.client import OpenAICompatibleEmbedding


def _make_valid_response_for_texts(texts: list[str]) -> Mock:
    """Return a mock httpx.Response with embeddings matching input count."""
    mock = Mock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": [0.1, 0.2, 0.3]}
            for i in range(len(texts))
        ],
        "model": "test-model",
    }
    mock.raise_for_status = Mock()
    return mock


def _make_side_effect_for_batch() -> Callable[..., Any]:
    """Create side_effect that returns vectors matching input count per chunk."""

    async def _side_effect(*args: object, **kwargs: object) -> Mock:
        body = dict(kwargs.get("json") or {})
        input_texts = body.get("input", [])
        return _make_valid_response_for_texts(input_texts)

    return _side_effect


@pytest.mark.asyncio
async def test_batch_size_smaller_than_total() -> None:
    """When total texts exceed batch_size, multiple API calls are made."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        batch_size=10,
        max_retries=1,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = _make_side_effect_for_batch()
    provider._client = mock_client

    texts: List[str] = [f"doc_{i}" for i in range(25)]
    results = await provider.embed_documents(texts)

    assert len(results) == 25
    # 25 texts with batch_size=10 → 3 API calls (10 + 10 + 5)
    assert mock_client.post.await_count == 3


@pytest.mark.asyncio
async def test_batch_size_exactly_total() -> None:
    """When total texts equals batch_size, only one API call is made."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        batch_size=8,
        max_retries=1,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = _make_side_effect_for_batch()
    provider._client = mock_client

    texts = [f"doc_{i}" for i in range(8)]
    results = await provider.embed_documents(texts)

    assert len(results) == 8
    assert mock_client.post.await_count == 1


@pytest.mark.asyncio
async def test_batch_size_larger_than_total() -> None:
    """When total texts is smaller than batch_size, only one API call."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        batch_size=100,
        max_retries=1,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = _make_side_effect_for_batch()
    provider._client = mock_client

    texts = [f"doc_{i}" for i in range(5)]
    results = await provider.embed_documents(texts)

    assert len(results) == 5
    assert mock_client.post.await_count == 1


@pytest.mark.asyncio
async def test_default_batch_size() -> None:
    """Default batch_size should be 16."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        max_retries=1,
    )
    assert provider.batch_size == 16