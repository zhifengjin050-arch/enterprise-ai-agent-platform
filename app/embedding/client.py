"""OpenAI-compatible embedding API client.

Implements EmbeddingProvider using httpx.AsyncClient to call
DeepSeek, Qwen, or any provider with an OpenAI-compatible /embeddings
endpoint.

Configuration sources (in priority order):
    - constructor kwargs (model, base_url, api_key)
    - app.core.config (embedding_api_base / llm_base_url, llm_api_key, embedding_model)

Retry strategy (exponential backoff):
    attempt 0 → 1s  |  attempt 1 → 3s  |  attempt 2 → 5s
    On 3 consecutive failures → EmbeddingConnectionError / EmbeddingAPIError.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.embedding.base import EmbeddingProvider
from app.embedding.exceptions import (
    EmbeddingAPIError,
    EmbeddingConfigurationError,
    EmbeddingConnectionError,
    EmbeddingError,
)

_RETRY_DELAYS: List[float] = [1.0, 3.0, 5.0]
_DEFAULT_BATCH_SIZE: int = 16


class OpenAICompatibleEmbedding(EmbeddingProvider):
    """Embedding provider for OpenAI-compatible APIs.

    Works with DeepSeek, Qwen, and any provider implementing the
    OpenAI ``POST /embeddings`` format.

    Batch embeddings are automatically chunked by ``batch_size``.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        max_retries: int = 3,
        timeout: float = 60.0,
    ) -> None:
        settings = get_settings()
        self.model = (
            model
            or settings.embedding_model
            or settings.llm_model
            or "text-embedding-ada-002"
        )
        self.base_url = (
            (base_url or settings.embedding_api_base or settings.llm_base_url)
            .rstrip("/")
            or "https://api.deepseek.com/v1"
        )
        self.api_key = api_key or settings.llm_api_key or settings.embedding_api_key or ""
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._dimension: int = settings.embedding_dimension or 1536

    # ------------------------------------------------------------------
    # Provider implementation
    # ------------------------------------------------------------------

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        results = await self.embed_documents([text])
        return results[0]

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings, auto-chunking by batch_size.

        Args:
            texts: Input texts.

        Returns:
            Embedding vectors in the same order as input.

        Raises:
            EmbeddingConfigurationError: If API key is missing.
            EmbeddingConnectionError: After all retries exhausted.
            EmbeddingAPIError: On non-retryable API errors (4xx).
        """
        if not texts:
            return []

        if not self.api_key:
            raise EmbeddingConfigurationError(
                field="api_key",
                message=(
                    "Embedding API key is not configured. "
                    "Set LLM_API_KEY or EMBEDDING_API_KEY in .env."
                ),
            )

        client = await self._get_client()
        # Chunk by batch_size for providers with input limits
        all_embeddings: List[List[float]] = []

        for start in range(0, len(texts), self.batch_size):
            chunk = texts[start : start + self.batch_size]
            vectors = await self._call_embeddings(client, chunk)
            all_embeddings.extend(vectors)

        return all_embeddings

    async def get_dimension(self) -> int:
        """Return embedding vector dimension."""
        return self._dimension

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def _call_embeddings(
        self,
        client: httpx.AsyncClient,
        texts: List[str],
    ) -> List[List[float]]:
        """POST /embeddings with retry + exponential backoff.

        Args:
            client: HTTP client.
            texts: Chunk of texts (size ≤ batch_size).

        Returns:
            Embedding vectors for this chunk.

        Raises:
            EmbeddingAPIError: If API returns 4xx (non-retryable).
            EmbeddingConnectionError: If all retries exhausted for 5xx / network errors.
        """
        last_error: Optional[EmbeddingError] = None

        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    "/embeddings",
                    json={"model": self.model, "input": texts},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )

                # Non-retryable client errors (bad request, auth, not found)
                if response.status_code in (400, 401, 403, 404, 422):
                    detail = _extract_error_detail(response)
                    raise EmbeddingAPIError(
                        status_code=response.status_code,
                        detail=detail,
                        retries=attempt,
                    )

                response.raise_for_status()
                data: Dict[str, Any] = response.json()

                # Sort by index to preserve input order
                items = sorted(data["data"], key=lambda x: x["index"])
                result: List[List[float]] = [item["embedding"] for item in items]

                if result:
                    self._dimension = len(result[0])

                return result

            except EmbeddingAPIError:
                # Non-retryable — re-raise immediately
                raise

            except httpx.HTTPStatusError as exc:
                # 5xx or unexpected status — retry
                last_error = EmbeddingConnectionError(
                    reason=(
                        f"HTTP {exc.response.status_code}: "
                        f"{_extract_error_detail(exc.response)}"
                    ),
                    retries=attempt + 1,
                )

            except httpx.RequestError as exc:
                last_error = EmbeddingConnectionError(
                    reason=str(exc),
                    retries=attempt + 1,
                )

            # Wait before next attempt (except on the last one)
            if attempt < self.max_retries - 1:
                delay = _RETRY_DELAYS[attempt] if attempt < len(_RETRY_DELAYS) else 5.0
                await asyncio.sleep(delay)

        # All retries exhausted
        assert last_error is not None
        raise last_error


def _extract_error_detail(response: httpx.Response) -> str:
    """Extract a human-readable error detail from an API response."""
    try:
        body = response.json()
        error = body.get("error", {})
        if isinstance(error, dict):
            return error.get("message", str(error))
        return str(error)
    except Exception:
        return response.text[:200]
