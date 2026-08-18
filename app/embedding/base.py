"""Embedding provider abstraction.

Defines the interface for all embedding providers used in the knowledge
platform's semantic search pipeline.

Usage in workflow:
    provider.embed_text(content)  →  single vector
    provider.embed_documents(texts)  →  batch vectors
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding providers.

    Implementations connect to DeepSeek, Qwen, or other OpenAI-compatible
    embedding APIs to convert text into vector representations for
    enterprise knowledge semantic search.

    All methods are async-first.
    """

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text string.

        Args:
            text: Input text to embed.

        Returns:
            Float vector (e.g. 1536 dimensions for ada-002).

        Raises:
            EmbeddingConfigurationError: If API key / model is missing.
            EmbeddingConnectionError: If the API is unreachable.
            EmbeddingAPIError: If the API returns an error.
        """
        ...

    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of texts.

        Implementations should handle:
        - Batches larger than the provider limit via internal chunking.
        - Exponential backoff retry on transient failures.
        - Empty input gracefully (return []).

        Args:
            texts: List of input texts (non-empty for real calls).

        Returns:
            List of embedding vectors, one per input text, in the same order.

        Raises:
            EmbeddingConfigurationError: If API key / model is missing.
            EmbeddingConnectionError: If the API is unreachable.
            EmbeddingAPIError: If the API returns an error.
        """
        ...

    @abstractmethod
    async def get_dimension(self) -> int:
        """Return the dimensionality of the embedding vectors.

        Returns:
            Integer dimension (1536 for text-embedding-ada-002).
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP client resources."""
        ...
