"""
Connector exception classes.

Replaces the legacy app/connector/exceptions.py hierarchy with
enterprise-grade exceptions that carry structured details.
"""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException


class ConnectorException(BaseAppException):
    """Base exception for all connector-related errors."""

    code: str = "CONNECTOR_ERROR"
    message: str = "A connector error occurred"
    http_status: int = 500


class ConnectorConfigError(ConnectorException):
    """Raised when the connector configuration is invalid or incomplete."""

    code: str = "CONNECTOR_CONFIG_ERROR"
    message: str = "Connector configuration is invalid"
    http_status: int = 400


class ConnectorAuthException(ConnectorException):
    """Raised when connector authentication with the external source fails."""

    code: str = "CONNECTOR_AUTH_FAILED"
    message: str = "Connector authentication failed"
    http_status: int = 401


class ConnectorConnectionException(ConnectorException):
    """Raised when a connection to the external source cannot be established."""

    code: str = "CONNECTOR_CONNECTION_ERROR"
    message: str = "Failed to connect to the external source"
    http_status: int = 502


class ConnectorSyncException(ConnectorException):
    """Raised when a connector sync operation fails."""

    code: str = "CONNECTOR_SYNC_ERROR"
    message: str = "Connector sync failed"
    http_status: int = 500
