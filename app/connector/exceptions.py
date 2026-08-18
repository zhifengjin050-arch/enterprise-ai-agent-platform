"""Connector exception classes.

All connector-specific exceptions now inherit from the enterprise
exception hierarchy (BaseAppException), ensuring consistent error
handling through the global exception handler.

These classes maintain backward compatibility with existing code
that catches ``ConnectorError`` or uses ``.source`` / ``.resource`` attributes.
"""
from __future__ import annotations

from typing import Any

from app.core.exceptions import BaseAppException


class ConnectorError(BaseAppException):
    """Base exception for all connector errors (backward compatible)."""

    code: str = "CONNECTOR_ERROR"
    message: str = "A connector error occurred"
    http_status: int = 500

    def __init__(
        self,
        message: str = "Connector error",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details or {"source": "unknown"})


class ConnectionError(ConnectorError):
    """Raised when a connection to the external source fails."""

    http_status: int = 502

    def __init__(
        self,
        source: str = "unknown",
        detail: str = "",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["source"] = source
        if detail:
            merged_details["detail"] = detail
        message = f"Failed to connect to {source}: {detail}" if detail else f"Failed to connect to {source}"
        super().__init__(message=message, details=merged_details)

    @property
    def source(self) -> str:
        """Backward-compatible attribute access."""
        return self.details.get("source", "unknown")


class AuthenticationError(ConnectorError):
    """Raised when authentication with the external source fails."""

    code: str = "CONNECTOR_AUTH_FAILED"
    http_status: int = 401

    def __init__(
        self,
        source: str = "unknown",
        detail: str = "",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["source"] = source
        if detail:
            merged_details["detail"] = detail
        message = f"Authentication failed for {source}: {detail}" if detail else f"Authentication failed for {source}"
        super().__init__(message=message, details=merged_details)

    @property
    def source(self) -> str:
        """Backward-compatible attribute access."""
        return self.details.get("source", "unknown")


class NotFoundError(ConnectorError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource: str = "resource",
        source: str = "unknown",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details.update({"resource": resource, "source": source})
        message = f"{resource} not found in {source}"
        super().__init__(message=message, details=merged_details)

    @property
    def resource(self) -> str:
        """Backward-compatible attribute access."""
        return self.details.get("resource", "")

    @property
    def source(self) -> str:
        """Backward-compatible attribute access."""
        return self.details.get("source", "unknown")


class SyncError(ConnectorError):
    """Raised when a sync operation fails."""

    code: str = "CONNECTOR_SYNC_ERROR"
    http_status: int = 500

    def __init__(
        self,
        source: str = "unknown",
        detail: str = "",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["source"] = source
        if detail:
            merged_details["detail"] = detail
        message = f"Sync failed for {source}: {detail}" if detail else f"Sync failed for {source}"
        super().__init__(message=message, details=merged_details)

    @property
    def source(self) -> str:
        """Backward-compatible attribute access."""
        return self.details.get("source", "unknown")
