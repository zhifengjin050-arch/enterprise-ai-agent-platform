"""
Database exception classes.

Wraps SQLAlchemy and database-level errors into structured
application exceptions, hiding implementation details
(e.g. constraint names, internal error messages) from API consumers.
"""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException


class DatabaseException(BaseAppException):
    """Base exception for all database-related errors.

    All database errors should be caught and re-raised as one of
    the subclasses, never exposed directly to API consumers.
    """

    code: str = "DATABASE_ERROR"
    message: str = "A database error occurred"
    http_status: int = 500


class DatabaseConnectionError(DatabaseException):
    """Raised when the database connection fails or times out."""

    code: str = "DATABASE_CONNECTION_ERROR"
    message: str = "Failed to connect to the database"
    http_status: int = 503


class DatabaseQueryError(DatabaseException):
    """Raised when a database query fails at runtime."""

    code: str = "DATABASE_QUERY_ERROR"
    message: str = "A database query failed"
    http_status: int = 500


class DatabaseIntegrityError(DatabaseException):
    """Raised on constraint violations (unique, FK, NOT NULL, etc.).

    Hides the underlying constraint name and detail to avoid
    leaking schema information to API consumers.
    """

    code: str = "DATABASE_CONSTRAINT_ERROR"
    message: str = "A data integrity constraint was violated"
    http_status: int = 409
