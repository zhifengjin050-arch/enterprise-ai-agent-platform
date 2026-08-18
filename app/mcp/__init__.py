"""MCP (Managed Cloud Provider / Model Context Protocol) 工具适配层.

Provides a bridge between external MCP tool servers (e.g. Enterprise DevOps MCP)
and the Agent Runtime ToolRegistry, enabling the Agent to invoke remote
infrastructure tools (Docker, K8s, SSH, Server Health, etc.).

Usage:
    from app.mcp import get_mcp_adapter_registry, mcp_tools_enabled
    registry = get_mcp_adapter_registry()
    tools = registry.list_adapter_names()
"""

from __future__ import annotations

from app.mcp.client import MCPClient
from app.mcp.registry import MCPAdapterRegistry, get_mcp_adapter_registry
from app.mcp.router import router as mcp_router
from app.mcp.tool_adapter import MCPToolAdapter

__all__ = [
    "MCPClient",
    "MCPToolAdapter",
    "MCPAdapterRegistry",
    "get_mcp_adapter_registry",
    "mcp_router",
    "mcp_tools_enabled",
]


def mcp_tools_enabled() -> bool:
    """Return whether MCP remote tools are configured and available."""
    from app.core.config import get_settings

    s = get_settings()
    return bool(s.mcp_server_url or s.enterprise_devops_mcp_url)
