"""Embedding service exceptions.

Now inherit from the enterprise exception hierarchy to ensure
consistent error handling through the global exception handler.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions.external import ExternalServiceException


class EmbeddingError(ExternalServiceException):
    """Base exception for embedding-related errors."""

    code: str = "EMBEDDING_ERROR"

    def __init__(
        self,
        message: str,
        *,
        retries: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.retries = retries
        merged_details = details or {}
        merged_details["retries"] = retries
        super().__init__(message=message, details=merged_details)


class EmbeddingAPIError(EmbeddingError):
    """Raised when the embedding API returns an error status."""

    code: str = "EMBEDDING_API_ERROR"

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        retries: int = 0,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(
            f"Embedding API returned {status_code}: {detail}",
            retries=retries,
        )


class EmbeddingConnectionError(EmbeddingError):
    """Raised when the embedding API is unreachable (network / timeout)."""

    code: str = "EMBEDDING_CONNECTION_ERROR"

    def __init__(self, reason: str, *, retries: int = 0) -> None:
        self.reason = reason
        super().__init__(
            f"Embedding API connection failed: {reason}",
            retries=retries,
        )


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when embedding settings are incomplete (missing key / model)."""

    code: str = "EMBEDDING_CONFIG_ERROR"

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message, details={"field": field})
