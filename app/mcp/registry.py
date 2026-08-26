"""Registry that discovers and wraps MCP tools from external servers.

Manages a collection of MCP server connections and adapts their exported
tools into the Agent Runtime's BaseTool interface for transparent invocation.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.agent_runtime.tools.registry import ToolRegistry
from app.mcp.client import MCPClient
from app.mcp.tool_adapter import MCPToolAdapter

logger = logging.getLogger(__name__)


class MCPAdapterRegistry:
    """Discovers and wraps MCP tools from external MCP servers.

    Typical lifecycle::

        registry = get_mcp_adapter_registry()
        registry.register_server("devops", "http://mcp:8080", api_key="...")
        await registry.discover_servers()
        registry.register_into(local_tool_registry)
        # ... application runs ...
        await registry.close_all()
    """

    def __init__(self) -> None:
        self._clients: Dict[str, MCPClient] = {}
        self._adapters: Dict[str, MCPToolAdapter] = {}

    # ------------------------------------------------------------------
    # Server management
    # ------------------------------------------------------------------

    def register_server(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
    ) -> None:
        """Register an MCP server client (discovery happens later).

        Args:
            name: Short identifier for the server (used in tool name prefixes).
            base_url: Base URL of the MCP HTTP API.
            api_key: Optional bearer token for authentication.
        """
        self._clients[name] = MCPClient(base_url, api_key)
        logger.info("Registered MCP server '%s' at %s", name, base_url)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover_servers(self) -> None:
        """Fetch tool lists from all registered servers and create adapters.

        This is an async operation that contacts every registered server.
        Servers that are unreachable or return errors are skipped with a
        warning — the application will not crash.
        """
        for server_name, client in self._clients.items():
            try:
                tools = await client.list_tools()
                for tool_info in tools or []:
                    tool_name = tool_info.get("name", "unknown")
                    adapter = MCPToolAdapter(
                        name=f"{server_name}_{tool_name}",
                        description=(tool_info.get("description") or "")[:200],
                        client=client,
                        input_schema=tool_info.get("inputSchema"),
                        original_tool_name=tool_name,
                    )
                    self._adapters[adapter.name] = adapter
                logger.info(
                    "Discovered %d tools from MCP server '%s'",
                    len(tools or []),
                    server_name,
                )
            except Exception as exc:
                logger.warning("MCP discover '%s' failed: %s", server_name, exc)

    # ------------------------------------------------------------------
    # Registration into local ToolRegistry
    # ------------------------------------------------------------------

    def register_into(self, tool_registry: ToolRegistry) -> None:
        """Register all MCP adapters into the local ToolRegistry.

        Adapters whose name already exists in the registry are silently
        skipped (log debug).
        """
        for adapter in self._adapters.values():
            try:
                tool_registry.register(adapter)
            except ValueError:
                logger.debug(
                    "MCP tool '%s' already registered, skipping",
                    adapter.name,
                )
                continue

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_adapter_names(self) -> List[str]:
        """Return names of all discovered MCP tool adapters."""
        return list(self._adapters.keys())

    def get_adapter(self, name: str) -> Optional[MCPToolAdapter]:
        """Return a specific adapter by its fully-qualified name."""
        return self._adapters.get(name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close_all(self) -> None:
        """Close all MCP client sessions (call on shutdown)."""
        for client in self._clients.values():
            await client.close()
        logger.info("All MCP clients closed")


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_registry: Optional[MCPAdapterRegistry] = None


def get_mcp_adapter_registry() -> MCPAdapterRegistry:
    """Return the lazy module-level MCPAdapterRegistry singleton."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = MCPAdapterRegistry()
    return _registry
