"""
Base exception class for the enterprise exception hierarchy.

All application exceptions should inherit from BaseAppException,
which provides structured fields for consistent error responses:

    {
        "success": false,
        "error": {
            "code": "CONNECTOR_AUTH_FAILED",
            "message": "Connector authentication failed",
            "details": {}
        },
        "request_id": "uuid"
    }
"""

from __future__ import annotations

from typing import Any


class BaseAppException(Exception):
    """Base exception for all application-level errors.

    Attributes:
        code: Machine-readable error code (e.g. "CONNECTOR_AUTH_FAILED").
        message: Human-readable error description.
        http_status: HTTP status code (e.g. 401, 404, 500).
        details: Additional structured context.
    """

    code: str = "INTERNAL_ERROR"
    message: str = "An internal error occurred"
    http_status: int = 500
    details: dict[str, Any] = {}

    def __init__(
        self,
        *,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if details is not None:
            self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a standard error dict."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
