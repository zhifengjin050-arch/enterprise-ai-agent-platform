"""Tests for embedding retry logic with exponential backoff."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.embedding.client import OpenAICompatibleEmbedding
from app.embedding.exceptions import EmbeddingConnectionError


@pytest.mark.asyncio
async def test_transient_failure_then_success() -> None:
    """Provider should recover after transient failures and return valid vectors."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        max_retries=3,
        timeout=5.0,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    call_count = 0

    async def _side_effect(*args: object, **kwargs: object) -> Mock:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # Fail with network error on first two attempts
            raise httpx.RequestError("connection reset")
        # Succeed on third attempt
        mock = Mock(spec=httpx.Response)
        mock.status_code = 200
        mock.json.return_value = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]},
            ],
            "model": "test-model",
        }
        mock.raise_for_status = Mock()
        return mock

    mock_client.post.side_effect = _side_effect
    provider._client = mock_client

    results = await provider.embed_documents(["hello"])
    assert len(results) == 1
    assert len(results[0]) == 2
    assert call_count == 3


@pytest.mark.asyncio
async def test_all_retries_exhausted() -> None:
    """Provider should raise EmbeddingConnectionError after exhausting retries."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        max_retries=3,
        timeout=5.0,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.RequestError("timeout")
    provider._client = mock_client

    with pytest.raises(EmbeddingConnectionError) as exc_info:
        await provider.embed_documents(["hello"])

    assert exc_info.value.retries == 3  # all 3 retries exhausted


@pytest.mark.asyncio
async def test_retry_delays_are_respected() -> None:
    """Verify that delays between retries follow the expected sequence."""
    import asyncio

    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        max_retries=3,
        timeout=5.0,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.RequestError("timeout")
    provider._client = mock_client

    start = asyncio.get_event_loop().time()
    with pytest.raises(EmbeddingConnectionError):
        await provider.embed_documents(["hello"])
    elapsed = asyncio.get_event_loop().time() - start

    # Expected delays: 1.0 + 3.0 = 4.0s (last attempt does not sleep)
    # Allow generous tolerance for CI/test environment
    assert elapsed >= 3.5, f"Expected ~4.0s delay, got {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_no_retry_on_4xx() -> None:
    """4xx errors should not be retried."""
    provider = OpenAICompatibleEmbedding(
        model="test",
        base_url="https://test.com",
        api_key="key",
        max_retries=3,
        timeout=5.0,
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    error_response = Mock(spec=httpx.Response)
    error_response.status_code = 401
    error_response.json.return_value = {"error": {"message": "unauthorized"}}
    mock_client.post.return_value = error_response
    provider._client = mock_client

    from app.embedding.exceptions import EmbeddingAPIError

    with pytest.raises(EmbeddingAPIError):
        await provider.embed_documents(["hello"])

    # Only one call — no retry
    assert mock_client.post.await_count == 1