"""
External service exception classes.

Handles errors from third-party APIs and external integrations.
"""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException


class ExternalServiceException(BaseAppException):
    """Base exception for all external service errors."""

    code: str = "EXTERNAL_SERVICE_ERROR"
    message: str = "An external service error occurred"
    http_status: int = 502


class ThirdPartyAPIError(ExternalServiceException):
    """Raised when a third-party API returns an error response."""

    code: str = "EXTERNAL_API_ERROR"
    message: str = "A third-party API returned an error"
    http_status: int = 502
