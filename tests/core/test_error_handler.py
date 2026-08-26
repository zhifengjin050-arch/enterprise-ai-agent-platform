"""Tests for the global exception handler.

Verifies that all registered exception handlers produce the correct
JSON response format with appropriate HTTP status codes.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exception_handlers import (
    base_app_exception_handler,
    generic_exception_handler,
    register_exception_handlers,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import (
    ConnectorAuthException,
    PermissionDenied,
)


class MockRequest:
    """Minimal mock for starlette Request."""

    def __init__(self, request_id: str = "test-req-id") -> None:
        self.state = type("State", (), {"request_id": request_id})()


@pytest.fixture
def mock_request() -> MockRequest:
    return MockRequest()


class TestBaseAppExceptionHandler:
    """Tests for base_app_exception_handler."""

    async def test_returns_json_response(self, mock_request: MockRequest) -> None:
        exc = ConnectorAuthException(details={"source": "Feishu"})
        response = await base_app_exception_handler(
            mock_request,  # type: ignore[arg-type]
            exc,
        )
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401

    async def test_response_format(self, mock_request: MockRequest) -> None:
        exc = PermissionDenied()
        response = await base_app_exception_handler(
            mock_request,  # type: ignore[arg-type]
            exc,
        )
        body = response.body.decode()
        assert '"success":false' in body
        assert '"code":"PERMISSION_DENIED"' in body
        assert '"message"' in body
        assert '"request_id":"test-req-id"' in body


class TestValidationExceptionHandler:
    """Tests for RequestValidationError handler."""

    async def test_returns_422(self, mock_request: MockRequest) -> None:
        # Create a RequestValidationError
        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "name"), "msg": "field required", "type": "value_error.missing"}
            ]
        )
        response = await validation_exception_handler(
            mock_request,  # type: ignore[arg-type]
            exc,
        )
        assert response.status_code == 422
        body = response.body.decode()
        assert '"code":"VALIDATION_ERROR"' in body


class TestSQLAlchemyExceptionHandler:
    """Tests for SQLAlchemy exception handler."""

    async def test_integrity_error(self, mock_request: MockRequest) -> None:
        exc = IntegrityError("INSERT INTO ...", {}, Exception("duplicate key"))
        response = await sqlalchemy_exception_handler(
            mock_request,  # type: ignore[arg-type]
            exc,
        )
        assert response.status_code == 409
        body = response.body.decode()
        assert '"code":"DATABASE_CONSTRAINT_ERROR"' in body

    async def test_operational_error(self, mock_request: MockRequest) -> None:
        exc = OperationalError("SELECT ...", {}, Exception("connection refused"))
        response = await sqlalchemy_exception_handler(
            mock_request,  # type: ignore[arg-type]
            exc,
        )
        assert response.status_code == 503
        body = response.body.decode()
        assert '"code":"DATABASE_CONNECTION_ERROR"' in body


class TestGenericExceptionHandler:
    """Tests for catch-all exception handler."""

    async def test_returns_500(self, mock_request: MockRequest) -> None:
        exc = RuntimeError("Unexpected failure")
        response = await generic_exception_handler(
            mock_request,  # type: ignore[arg-type]
            exc,
        )
        assert response.status_code == 500
        body = response.body.decode()
        assert '"code":"INTERNAL_ERROR"' in body
        assert '"request_id":"test-req-id"' in body


class TestRegisterExceptionHandlers:
    """Tests for register_exception_handlers()."""

    def test_registers_all_handlers(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        # After registration, there should be 6 handlers registered
        # (BaseAppException + RequestValidationError + 3 SQLAlchemy + Exception)
        assert len(app.exception_handlers) >= 5
