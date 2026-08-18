"""
Unified API response schema.

Provides standard success and error response structures for all
API endpoints, ensuring consistent JSON output across the application.

Success format:
    {
        "success": true,
        "data": { ... }
    }

Error format:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "details": {}
        },
        "request_id": "uuid"
    }
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """Standard error detail structure."""

    code: str
    message: str
    details: dict[str, Any] = {}


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success response envelope."""

    success: bool = True
    data: DataT


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: bool = False
    error: ErrorDetail
    request_id: str = ""


def success_response(
    data: Any,
) -> dict[str, Any]:
    """Build a standard success response dict.

    Args:
        data: The payload to return.

    Returns:
        A dict matching the SuccessResponse schema.
    """
    return {"success": True, "data": data}


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    """Build a standard error response dict.

    Args:
        code: Machine-readable error code.
        message: Human-readable description.
        details: Optional structured context.
        request_id: Unique request identifier.

    Returns:
        A dict matching the ErrorResponse schema.
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "request_id": request_id,
    }
