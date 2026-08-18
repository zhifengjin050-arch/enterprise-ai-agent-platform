"""
Enterprise exception architecture.

Provides a unified exception hierarchy for the entire application.
All exceptions inherit from BaseAppException, ensuring consistent
error codes, messages, HTTP status codes, and detail payloads.

Usage:
    raise ConnectorAuthException(
        details={"connector_id": "feishu-1", "source": "feishu"}
    )
"""

from app.core.exceptions.agent import (
    AgentException,
    AgentExecutionException,
    AgentNotFoundException,
    AgentPermissionException,
    LLMQuotaException,
    ToolNotFoundException,
    ToolPermissionException,
)
from app.core.exceptions.auth import (
    AuthException,
    InvalidToken,
    TokenExpired,
)
from app.core.exceptions.base import BaseAppException
from app.core.exceptions.connector import (
    ConnectorAuthException,
    ConnectorConfigError,
    ConnectorConnectionException,
    ConnectorException,
    ConnectorSyncException,
)
from app.core.exceptions.database import (
    DatabaseConnectionError,
    DatabaseException,
    DatabaseIntegrityError,
    DatabaseQueryError,
)
from app.core.exceptions.external import (
    ExternalServiceException,
    ThirdPartyAPIError,
)
from app.core.exceptions.permission import (
    PermissionDenied,
    PermissionException,
)
from app.core.exceptions.validation import (
    InvalidParameter,
    ValidationException,
)

__all__ = [
    "BaseAppException",
    "DatabaseException",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    "DatabaseIntegrityError",
    "ConnectorException",
    "ConnectorConfigError",
    "ConnectorAuthException",
    "ConnectorSyncException",
    "ConnectorConnectionException",
    "AuthException",
    "InvalidToken",
    "TokenExpired",
    "PermissionException",
    "PermissionDenied",
    "ValidationException",
    "InvalidParameter",
    "ExternalServiceException",
    "ThirdPartyAPIError",
    "AgentException",
    "AgentPermissionException",
    "ToolPermissionException",
    "LLMQuotaException",
    "AgentNotFoundException",
    "ToolNotFoundException",
    "AgentExecutionException",
]
