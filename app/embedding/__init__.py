"""
Embedding service package.

Provides text embedding capabilities for semantic search within the
knowledge platform. Supports DeepSeek, Qwen, and OpenAI-compatible
embedding APIs through a unified EmbeddingProvider interface.

Package public API:
    EmbeddingProvider       — abstract base class
    OpenAICompatibleEmbedding — httpx-based OpenAI-style implementation
    EmbeddingError           — base exception
    EmbeddingAPIError        — API error response
    EmbeddingConnectionError — network failure
    EmbeddingConfigurationError — missing key/model
"""

from app.embedding.base import EmbeddingProvider
from app.embedding.client import OpenAICompatibleEmbedding
from app.embedding.exceptions import (
    EmbeddingAPIError,
    EmbeddingConfigurationError,
    EmbeddingConnectionError,
    EmbeddingError,
)

__all__ = [
    "EmbeddingProvider",
    "OpenAICompatibleEmbedding",
    "EmbeddingAPIError",
    "EmbeddingConfigurationError",
    "EmbeddingConnectionError",
    "EmbeddingError",
]
