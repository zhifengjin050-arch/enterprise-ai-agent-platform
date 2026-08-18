"""
Global exception handlers for FastAPI.

Registers handlers that convert all exception types into the
unified error response format.

Mapped exceptions:
    - BaseAppException (and all subclasses)
    - FastAPI RequestValidationError
    - SQLAlchemy database exceptions
    - Generic Exception (catch-all)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
)
from sqlalchemy.exc import (
    TimeoutError as SA_TimeoutError,
)

from app.core.exceptions import BaseAppException
from app.core.exceptions.database import (
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseQueryError,
)
from app.core.response import error_response

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    """Extract request_id from request state."""
    return getattr(request.state, "request_id", "")


async def base_app_exception_handler(
    request: Request,
    exc: BaseAppException,
) -> JSONResponse:
    """Handle all BaseAppException subclasses."""
    request_id = _get_request_id(request)
    logger.warning(
        "Application error: code=%s message=%s",
        exc.code,
        exc.message,
        extra={"request_id": request_id, "error_code": exc.code},
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle FastAPI request validation errors."""
    request_id = _get_request_id(request)
    errors = exc.errors()
    logger.warning(
        "Validation error: %s",
        errors,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=422,
        content=error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": errors},
            request_id=request_id,
        ),
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle SQLAlchemy database exceptions.

    Maps specific SQLAlchemy exceptions to our enterprise exceptions
    and hides internal database details.
    """
    request_id = _get_request_id(request)
    logger.error(
        "Database error: %s",
        str(exc),
        extra={"request_id": request_id},
        exc_info=True,
    )

    if isinstance(exc, IntegrityError):
        db_exc = DatabaseIntegrityError()
    elif isinstance(exc, OperationalError):
        db_exc = DatabaseConnectionError(
            details={"db_dialect": str(exc.connection_invalidated)}
        )
    elif isinstance(exc, SA_TimeoutError):
        db_exc = DatabaseConnectionError(
            message="Database query timed out",
            details={"timeout": True},
        )
    else:
        db_exc = DatabaseQueryError()

    return JSONResponse(
        status_code=db_exc.http_status,
        content=error_response(
            code=db_exc.code,
            message=db_exc.message,
            request_id=request_id,
        ),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Logs the full traceback but returns a sanitised error to the client.
    """
    request_id = _get_request_id(request)
    logger.error(
        "Unhandled exception: %s",
        str(exc),
        extra={"request_id": request_id},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=error_response(
            code="INTERNAL_ERROR",
            message="An unexpected internal error occurred",
            request_id=request_id,
        ),
    )


def register_exception_handlers(app: Any) -> None:
    """Register all exception handlers on the FastAPI app.

    Call during application startup after creating the FastAPI instance.

    Args:
        app: The FastAPI application instance.
    """
    app.add_exception_handler(BaseAppException, base_app_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    # SQLAlchemy exceptions (catch multiple via generic handler)
    app.add_exception_handler(IntegrityError, sqlalchemy_exception_handler)
    app.add_exception_handler(OperationalError, sqlalchemy_exception_handler)
    app.add_exception_handler(SA_TimeoutError, sqlalchemy_exception_handler)
    # Catch-all must be registered last
    app.add_exception_handler(Exception, generic_exception_handler)
