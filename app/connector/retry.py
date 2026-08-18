"""Connector error recovery — retry policy for transient failures.

Provides a configurable retry policy that distinguishes between
retryable errors (network timeouts, server errors) and non-retryable
errors (authentication failures, invalid config) to avoid needless retries.

Usage:
    policy = ConnectorRetryPolicy(max_retries=3, backoff_base=1.0)
    result = await policy.execute(coroutine_fn)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Type

from app.core.exceptions import (
    ConnectorAuthException,
    ConnectorConfigError,
    ConnectorConnectionException,
    ConnectorException,
)

logger = logging.getLogger(__name__)


# ── Error classification ──

# Errors that SHOULD be retried (transient / recoverable)
RETRYABLE_ERRORS: tuple[Type[Exception], ...] = (
    ConnectorConnectionException,
    TimeoutError,
    ConnectionError,
    OSError,
)

# Errors that MUST NOT be retried (permanent)
NON_RETRYABLE_ERRORS: tuple[Type[Exception], ...] = (
    ConnectorAuthException,
    ConnectorConfigError,
)


def is_retryable(exc: Exception) -> bool:
    """Determine whether an exception represents a transient failure.

    Args:
        exc: The exception to classify.

    Returns:
        True if the error is retryable, False otherwise.
    """
    if isinstance(exc, NON_RETRYABLE_ERRORS):
        return False
    if isinstance(exc, RETRYABLE_ERRORS):
        return True
    # For raw httpx / aiohttp / generic errors, treat connection errors as retryable
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    # Everything else (including unknown) is NOT retryable by default
    return False


class ConnectorRetryPolicy:
    """Configurable retry policy for connector operations.

    Implements exponential backoff with jitter for retryable errors.
    Non-retryable errors are raised immediately.

    Attributes:
        max_retries: Maximum number of retry attempts (default 3).
        backoff_base: Base multiplier for exponential backoff in seconds (default 1.0).
        backoff_max: Maximum backoff delay in seconds (default 30.0).
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

    def to_dict(self) -> dict[str, Any]:
        """Serialize policy configuration for API responses."""
        return {
            "max_retries": self.max_retries,
            "backoff_base": self.backoff_base,
            "backoff_max": self.backoff_max,
        }

    async def execute(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        *,
        context: str = "",
    ) -> Any:
        """Execute a coroutine with retry logic.

        Args:
            coro_factory: A zero-argument callable that returns a coroutine.
            context: Optional description for logging (e.g., operation name).

        Returns:
            The result of the coroutine.

        Raises:
            ConnectorException: If all retries are exhausted for a retryable error,
                or immediately for a non-retryable error.
        """
        last_exc: Exception | None = None

        for attempt in range(1 + self.max_retries):
            try:
                return await coro_factory()
            except Exception as exc:
                last_exc = exc

                if not is_retryable(exc):
                    logger.warning(
                        "Non-retryable error in %s (attempt %d/%d): %s",
                        context or "connector operation",
                        attempt,
                        1 + self.max_retries,
                        exc,
                    )
                    raise

                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retryable error in %s (attempt %d/%d, retrying in %.2fs): %s",
                        context or "connector operation",
                        attempt,
                        1 + self.max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise ConnectorException(
            message=(
                f"Operation '{context or 'connector operation'}' failed after "
                f"{self.max_retries} retries: {last_exc}"
            ),
            details={
                "max_retries": self.max_retries,
                "last_error": str(last_exc),
            },
        ) from last_exc

    def _backoff_delay(self, attempt: int) -> float:
        """Compute exponential backoff delay with jitter.

        Args:
            attempt: The zero-based attempt number.

        Returns:
            Delay in seconds.
        """
        import random

        delay = min(self.backoff_max, self.backoff_base * (2**attempt))
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter


# Module-level default policy
default_retry_policy = ConnectorRetryPolicy()
