"""Tests for the enterprise exception hierarchy.

Covers all exception classes in app/core/exceptions/:
- BaseAppException
- All sub-exceptions (Database, Connector, Auth, Permission, Validation, External)
- to_dict() serialization
- HTTP status codes
- Error code strings
"""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    AuthException,
    BaseAppException,
    ConnectorAuthException,
    ConnectorConfigError,
    ConnectorConnectionException,
    ConnectorException,
    ConnectorSyncException,
    DatabaseConnectionError,
    DatabaseException,
    DatabaseIntegrityError,
    DatabaseQueryError,
    ExternalServiceException,
    InvalidParameter,
    InvalidToken,
    PermissionDenied,
    PermissionException,
    ThirdPartyAPIError,
    TokenExpired,
    ValidationException,
)


class TestBaseAppException:
    """Tests for BaseAppException."""

    def test_default_values(self) -> None:
        """Base exception should have sensible defaults."""
        exc = BaseAppException()
        assert exc.code == "INTERNAL_ERROR"
        assert exc.message == "An internal error occurred"
        assert exc.http_status == 500
        assert exc.details == {}

    def test_custom_message(self) -> None:
        """Should accept a custom message."""
        exc = BaseAppException(message="Custom error")
        assert exc.message == "Custom error"

    def test_custom_details(self) -> None:
        """Should accept custom details dict."""
        exc = BaseAppException(details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_to_dict(self) -> None:
        """to_dict() should produce the standard error format."""
        exc = BaseAppException(
            message="Something broke",
            details={"field": "name"},
        )
        d = exc.to_dict()
        assert d["code"] == "INTERNAL_ERROR"
        assert d["message"] == "Something broke"
        assert d["details"] == {"field": "name"}

    def test_is_exception(self) -> None:
        """BaseAppException should be a real Exception subclass."""
        exc = BaseAppException()
        assert isinstance(exc, Exception)
        assert isinstance(exc, BaseException)


class TestDatabaseExceptions:
    """Tests for DatabaseException hierarchy."""

    def test_base_database(self) -> None:
        exc = DatabaseException()
        assert exc.code == "DATABASE_ERROR"
        assert exc.http_status == 500

    def test_connection_error(self) -> None:
        exc = DatabaseConnectionError()
        assert exc.code == "DATABASE_CONNECTION_ERROR"
        assert exc.http_status == 503

    def test_query_error(self) -> None:
        exc = DatabaseQueryError()
        assert exc.code == "DATABASE_QUERY_ERROR"
        assert exc.http_status == 500

    def test_integrity_error(self) -> None:
        exc = DatabaseIntegrityError()
        assert exc.code == "DATABASE_CONSTRAINT_ERROR"
        assert exc.http_status == 409

    def test_inheritance(self) -> None:
        """All DB exceptions should be instanceof DatabaseException."""
        assert isinstance(DatabaseConnectionError(), DatabaseException)
        assert isinstance(DatabaseQueryError(), DatabaseException)
        assert isinstance(DatabaseIntegrityError(), DatabaseException)
        assert isinstance(DatabaseException(), BaseAppException)


class TestConnectorExceptions:
    """Tests for ConnectorException hierarchy."""

    def test_base_connector(self) -> None:
        exc = ConnectorException()
        assert exc.code == "CONNECTOR_ERROR"
        assert exc.http_status == 500

    def test_config_error(self) -> None:
        exc = ConnectorConfigError()
        assert exc.code == "CONNECTOR_CONFIG_ERROR"
        assert exc.http_status == 400

    def test_auth_failed(self) -> None:
        exc = ConnectorAuthException()
        assert exc.code == "CONNECTOR_AUTH_FAILED"
        assert exc.http_status == 401

    def test_connection_error(self) -> None:
        exc = ConnectorConnectionException()
        assert exc.code == "CONNECTOR_CONNECTION_ERROR"
        assert exc.http_status == 502

    def test_sync_error(self) -> None:
        exc = ConnectorSyncException()
        assert exc.code == "CONNECTOR_SYNC_ERROR"
        assert exc.http_status == 500

    def test_custom_details(self) -> None:
        exc = ConnectorAuthException(
            message="Feishu auth failed",
            details={"source": "Feishu", "status_code": 401},
        )
        assert exc.details["source"] == "Feishu"


class TestAuthExceptions:
    """Tests for AuthException hierarchy."""

    def test_base_auth(self) -> None:
        exc = AuthException()
        assert exc.code == "AUTH_ERROR"
        assert exc.http_status == 401

    def test_invalid_token(self) -> None:
        exc = InvalidToken()
        assert exc.code == "AUTH_INVALID_TOKEN"
        assert exc.http_status == 401

    def test_token_expired(self) -> None:
        exc = TokenExpired()
        assert exc.code == "AUTH_TOKEN_EXPIRED"
        assert exc.http_status == 401


class TestPermissionExceptions:
    """Tests for PermissionException hierarchy."""

    def test_base_permission(self) -> None:
        exc = PermissionException()
        assert exc.code == "PERMISSION_ERROR"
        assert exc.http_status == 403

    def test_permission_denied(self) -> None:
        exc = PermissionDenied()
        assert exc.code == "PERMISSION_DENIED"
        assert exc.http_status == 403


class TestValidationExceptions:
    """Tests for ValidationException hierarchy."""

    def test_base_validation(self) -> None:
        exc = ValidationException()
        assert exc.code == "VALIDATION_ERROR"
        assert exc.http_status == 422

    def test_invalid_parameter(self) -> None:
        exc = InvalidParameter()
        assert exc.code == "VALIDATION_INVALID_PARAMETER"
        assert exc.http_status == 422


class TestExternalServiceExceptions:
    """Tests for ExternalServiceException hierarchy."""

    def test_base_external(self) -> None:
        exc = ExternalServiceException()
        assert exc.code == "EXTERNAL_SERVICE_ERROR"
        assert exc.http_status == 502

    def test_third_party_api(self) -> None:
        exc = ThirdPartyAPIError()
        assert exc.code == "EXTERNAL_API_ERROR"
        assert exc.http_status == 502


class TestLegacyConnectorCompatibility:
    """Tests that legacy connector exceptions still work via new hierarchy."""

    def test_legacy_connector_error(self) -> None:
        from app.connector.exceptions import ConnectorError

        exc = ConnectorError("Legacy error")
        assert isinstance(exc, BaseAppException)
        assert exc.code == "CONNECTOR_ERROR"
        assert exc.message == "Legacy error"

    def test_legacy_connection_error(self) -> None:
        from app.connector.exceptions import ConnectionError

        exc = ConnectionError(source="Feishu", detail="timeout")
        assert isinstance(exc, BaseAppException)
        assert exc.http_status == 502
        assert "Feishu" in exc.message
        assert exc.source == "Feishu"

    def test_legacy_auth_error(self) -> None:
        from app.connector.exceptions import AuthenticationError

        exc = AuthenticationError(source="GitLab")
        assert isinstance(exc, BaseAppException)
        assert exc.code == "CONNECTOR_AUTH_FAILED"
        assert exc.http_status == 401
        assert exc.source == "GitLab"

    def test_legacy_not_found_error(self) -> None:
        from app.connector.exceptions import NotFoundError

        exc = NotFoundError(resource="wiki", source="GitLab")
        assert isinstance(exc, BaseAppException)
        assert exc.http_status == 500

    def test_legacy_sync_error(self) -> None:
        from app.connector.exceptions import SyncError

        exc = SyncError(source="Feishu", detail="rate limit")
        assert isinstance(exc, BaseAppException)
        assert exc.code == "CONNECTOR_SYNC_ERROR"