"""Tests for unified API response schema.

Verifies:
1. SuccessResponse format
2. ErrorResponse format
3. success_response() and error_response() helper functions
"""

from __future__ import annotations

from app.core.response import (
    ErrorDetail,
    ErrorResponse,
    SuccessResponse,
    error_response,
    success_response,
)


class TestSuccessResponse:
    """Tests for success response format."""

    def test_success_response_dict(self) -> None:
        result = success_response(data={"key": "value"})
        assert result["success"] is True
        assert result["data"] == {"key": "value"}

    def test_success_response_list(self) -> None:
        result = success_response(data=[1, 2, 3])
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]

    def test_success_pydantic_model(self) -> None:
        model = SuccessResponse(data={"name": "test"})
        assert model.success is True
        assert model.data == {"name": "test"}


class TestErrorResponse:
    """Tests for error response format."""

    def test_error_response_dict(self) -> None:
        result = error_response(
            code="CONNECTOR_AUTH_FAILED",
            message="Auth failed",
            details={"source": "Feishu"},
            request_id="req-123",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "CONNECTOR_AUTH_FAILED"
        assert result["error"]["message"] == "Auth failed"
        assert result["error"]["details"] == {"source": "Feishu"}
        assert result["request_id"] == "req-123"

    def test_error_response_minimal(self) -> None:
        result = error_response(code="ERROR", message="Something broke")
        assert result["success"] is False
        assert result["error"]["details"] == {}
        assert result["request_id"] == ""

    def test_error_detail_model(self) -> None:
        detail = ErrorDetail(code="ERR", message="msg", details={"k": "v"})
        assert detail.code == "ERR"
        assert detail.details == {"k": "v"}

    def test_error_response_model(self) -> None:
        response = ErrorResponse(
            error=ErrorDetail(code="ERR", message="msg"),
            request_id="req-123",
        )
        assert response.success is False
        assert response.error.code == "ERR"
        assert response.request_id == "req-123"