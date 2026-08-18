"""
Authentication exception classes.

Handles JWT token validation, login, and identity errors.
"""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException


class AuthException(BaseAppException):
    """Base exception for all authentication-related errors."""

    code: str = "AUTH_ERROR"
    message: str = "An authentication error occurred"
    http_status: int = 401


class InvalidToken(AuthException):
    """Raised when the provided token is malformed or invalid."""

    code: str = "AUTH_INVALID_TOKEN"
    message: str = "The provided token is invalid"
    http_status: int = 401


class TokenExpired(AuthException):
    """Raised when the provided token has expired."""

    code: str = "AUTH_TOKEN_EXPIRED"
    message: str = "The provided token has expired"
    http_status: int = 401
