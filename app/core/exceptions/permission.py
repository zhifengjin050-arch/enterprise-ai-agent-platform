"""
Permission / authorization exception classes.

Handles RBAC and resource-level access control errors.
"""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException


class PermissionException(BaseAppException):
    """Base exception for all permission-related errors."""

    code: str = "PERMISSION_ERROR"
    message: str = "A permission error occurred"
    http_status: int = 403


class PermissionDenied(PermissionException):
    """Raised when the user lacks the required permission for an action."""

    code: str = "PERMISSION_DENIED"
    message: str = "You do not have permission to perform this action"
    http_status: int = 403
