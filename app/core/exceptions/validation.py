"""
Validation exception classes.

Handles input validation, parameter checking, and request parsing errors.
"""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException


class ValidationException(BaseAppException):
    """Base exception for all validation-related errors."""

    code: str = "VALIDATION_ERROR"
    message: str = "A validation error occurred"
    http_status: int = 422


class InvalidParameter(ValidationException):
    """Raised when a request parameter is invalid or missing."""

    code: str = "VALIDATION_INVALID_PARAMETER"
    message: str = "An invalid parameter was provided"
    http_status: int = 422
