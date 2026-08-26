"""Tests for the OpenAI-compatible embedding client."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.embedding.client import OpenAICompatibleEmbedding
from app.embedding.exceptions import (
    EmbeddingAPIError,
    EmbeddingConfigurationError,
    EmbeddingConnectionError,
)


@pytest.fixture
def mock_httpx_response() -> Mock:
    """Build a mock httpx.Response that returns a valid embedding payload."""
    mock = Mock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = {
        "object": "list",
        "data": [
            {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"object": "embedding", "index": 1, "embedding": [0.4, 0.5, 0.6]},
        ],
        "model": "test-model",
        "usage": {"prompt_tokens": 4, "total_tokens": 4},
    }
    mock.raise_for_status = Mock()
    return mock


@pytest.fixture
def provider_with_mock_client(mock_httpx_response: Mock) -> OpenAICompatibleEmbedding:
    """Return an OpenAICompatibleEmbedding whose HTTP client mock returns a valid response."""
    provider = OpenAICompatibleEmbedding(
        model="test-model",
        base_url="https://api.test.com/v1",
        api_key="test-key",
        batch_size=16,
        max_retries=1,
        timeout=5.0,
    )
    # Replace the real AsyncClient with a mock
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_httpx_response
    provider._client = mock_client
    provider._dimension = 3
    return provider


class TestOpenAICompatibleEmbedding:
    """Tests for the client implementation."""

    @pytest.mark.asyncio
    async def test_embed_text_single(
        self, provider_with_mock_client: OpenAICompatibleEmbedding
    ) -> None:
        """embed_text should return a single vector."""
        vector = await provider_with_mock_client.embed_text("Hello world")
        assert isinstance(vector, list)
        assert len(vector) == 3

    @pytest.mark.asyncio
    async def test_embed_documents_multiple(
        self,
        provider_with_mock_client: OpenAICompatibleEmbedding,
    ) -> None:
        """embed_documents should return correct number of vectors."""
        texts = ["first document", "second document"]
        vectors = await provider_with_mock_client.embed_documents(texts)
        assert len(vectors) == 2
        assert all(len(v) == 3 for v in vectors)

    @pytest.mark.asyncio
    async def test_empty_input(self, provider_with_mock_client: OpenAICompatibleEmbedding) -> None:
        """Empty input should return empty list."""
        result = await provider_with_mock_client.embed_documents([])
        assert result == []

    @pytest.mark.asyncio
    async def test_request_format(
        self, provider_with_mock_client: OpenAICompatibleEmbedding
    ) -> None:
        """Verify correct POST body and headers are sent."""
        mock_client = provider_with_mock_client._client
        assert mock_client is not None

        await provider_with_mock_client.embed_documents(["test"])

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        # url is the first positional argument
        assert call_args[0][0] == "/embeddings"
        assert call_args[1]["json"]["model"] == "test-model"
        assert call_args[1]["json"]["input"] == ["test"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_response_parsing_maintains_order(
        self,
        provider_with_mock_client: OpenAICompatibleEmbedding,
    ) -> None:
        """Vectors should be returned in the same order as input texts, even if API reorders."""
        mock_client = provider_with_mock_client._client
        assert mock_client is not None

        # Simulate out-of-order response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 1, "embedding": [0.9, 0.8, 0.7]},
                {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]},
            ],
            "model": "test-model",
        }
        mock_response.raise_for_status = Mock()
        mock_client.post.return_value = mock_response

        vectors = await provider_with_mock_client.embed_documents(["a", "b"])
        assert vectors[0] == [0.1, 0.2, 0.3]  # index 0 → first input
        assert vectors[1] == [0.9, 0.8, 0.7]  # index 1 → second input

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_configuration_error(self) -> None:
        """Provider without API key should raise EmbeddingConfigurationError."""
        provider = OpenAICompatibleEmbedding(
            model="test",
            base_url="https://test.com",
            api_key="",
            max_retries=1,
        )
        with pytest.raises(EmbeddingConfigurationError):
            await provider.embed_documents(["text"])

    @pytest.mark.asyncio
    async def test_400_response_raises_api_error(self) -> None:
        """4xx responses should raise EmbeddingAPIError immediately (no retry)."""
        provider = OpenAICompatibleEmbedding(
            model="test",
            base_url="https://test.com",
            api_key="key",
            max_retries=3,
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        error_response = Mock(spec=httpx.Response)
        error_response.status_code = 400
        error_response.json.return_value = {"error": {"message": "bad request"}}
        mock_client.post.return_value = error_response
        provider._client = mock_client

        with pytest.raises(EmbeddingAPIError) as exc_info:
            await provider.embed_documents(["text"])
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_503_response_retries_then_raises_connection_error(self) -> None:
        """5xx responses should trigger retries, then raise EmbeddingConnectionError."""
        provider = OpenAICompatibleEmbedding(
            model="test",
            base_url="https://test.com",
            api_key="key",
            max_retries=2,
            timeout=5.0,
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        error_response = Mock(spec=httpx.Response)
        error_response.status_code = 503
        error_response.text = "Service Unavailable"
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 error",
            request=Mock(),
            response=error_response,
        )
        mock_client.post.return_value = error_response
        provider._client = mock_client

        with pytest.raises(EmbeddingConnectionError) as exc_info:
            await provider.embed_documents(["text"])
        assert exc_info.value.retries == 2  # exhausted both retries
