"""MCP server discovery — auto-register from config."""

from __future__ import annotations

import logging

from app.agent_runtime.tools.registry import get_tool_registry
from app.core.config import get_settings
from app.mcp import get_mcp_adapter_registry

logger = logging.getLogger(__name__)


async def discover_and_register_all_mcp_servers() -> None:
    """Read settings, connect to MCP servers, discover tools, and register adapters."""

    settings = get_settings()
    registry = get_mcp_adapter_registry()
    tool_registry = get_tool_registry()

    # 1. Enterprise DevOps MCP Server (Project 2)
    if settings.enterprise_devops_mcp_url:
        registry.register_server(
            name="enterprise_devops",
            base_url=settings.enterprise_devops_mcp_url,
            api_key=settings.mcp_api_key,
        )
        logger.info("MCP: Registered enterprise_devops server at %s", settings.enterprise_devops_mcp_url)

    # 2. Generic MCP Server
    if settings.mcp_server_url:
        registry.register_server(
            name="mcp",
            base_url=settings.mcp_server_url,
            api_key=settings.mcp_api_key,
        )
        logger.info("MCP: Registered generic MCP server at %s", settings.mcp_server_url)

    # 3. Discover tools from all registered servers
    if registry._clients:
        await registry.discover_servers()
        registry.register_into(tool_registry)
        logger.info(
            "MCP: Discovered and registered %d tools",
            len(registry.list_adapter_names()),
        )
        for name in registry.list_adapter_names():
            logger.debug("MCP: Tool registered — %s", name)
    else:
        logger.info("MCP: No servers configured, skipping discovery")
