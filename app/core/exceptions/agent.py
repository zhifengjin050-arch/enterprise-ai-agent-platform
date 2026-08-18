"""Agent / LLM / Tool exceptions for Phase 6 Agent Runtime."""

from __future__ import annotations

from app.core.exceptions.base import BaseAppException
from app.core.exceptions.external import ExternalServiceException
from app.core.exceptions.permission import PermissionException


class AgentException(BaseAppException):
    """Base exception for Agent Runtime errors."""

    code: str = "AGENT_ERROR"
    message: str = "An agent runtime error occurred"
    http_status: int = 500


class AgentPermissionException(PermissionException):
    """Raised when the caller lacks permission to run an agent or tool."""

    code: str = "AGENT_PERMISSION_DENIED"
    message: str = "Agent permission denied"
    http_status: int = 403


class ToolPermissionException(PermissionException):
    """Raised when a tool cannot be executed due to missing permission."""

    code: str = "TOOL_PERMISSION_DENIED"
    message: str = "Tool permission denied"
    http_status: int = 403


class LLMQuotaException(ExternalServiceException):
    """Raised when LLM quota / rate limit is exceeded."""

    code: str = "LLM_QUOTA_EXCEEDED"
    message: str = "LLM quota exceeded"
    http_status: int = 429


class AgentNotFoundException(AgentException):
    """Raised when an agent or task is not found."""

    code: str = "AGENT_NOT_FOUND"
    message: str = "Agent or task not found"
    http_status: int = 404


class ToolNotFoundException(AgentException):
    """Raised when a requested tool is not registered."""

    code: str = "TOOL_NOT_FOUND"
    message: str = "Tool not found"
    http_status: int = 404


class AgentExecutionException(AgentException):
    """Raised when agent execution fails."""

    code: str = "AGENT_EXECUTION_FAILED"
    message: str = "Agent execution failed"
    http_status: int = 500
