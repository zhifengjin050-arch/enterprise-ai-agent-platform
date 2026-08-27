"""Adapts a remote MCP tool into the local BaseTool interface.

Allows the Agent Runtime to invoke tools hosted on external MCP servers
as if they were local tools, with proper permission scoping
(``mcp`` and ``mcp:<tool-name>``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult
from app.mcp.client import MCPClient


class MCPToolAdapter(BaseTool):
    """Wraps a remote MCP tool to behave as a local Agent tool.

    The adapter stores both a fully-qualified local name
    (``{server_name}_{tool_name}``) for the ToolRegistry and the original
    remote tool name so that ``execute()`` forwards the call correctly.
    """

    def __init__(
        self,
        name: str,
        description: str,
        client: MCPClient,
        input_schema: Optional[Dict[str, Any]] = None,
        original_tool_name: Optional[str] = None,
    ) -> None:
        self.name = name
        self.description = description
        self._client = client
        self._input_schema = input_schema or {}
        self._original_tool_name = original_tool_name or name
        self.permissions = ["mcp", f"mcp:{name}"]

    async def execute(self, input: Dict[str, Any], context: ToolContext) -> ToolResult:
        """Forward execution to the remote MCP server with caller identity headers."""
        from app.security.dlp import is_blocked_mcp_tool, redact_tool_payload

        if is_blocked_mcp_tool(self._original_tool_name) or is_blocked_mcp_tool(self.name):
            return ToolResult(
                success=False,
                error="This tool is blocked from chat. Use Vault / PAM / an approved workflow.",
            )
        identity = {
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
            "organization_id": context.organization_id,
        }
        try:
            result = await self._client.execute_tool(
                self._original_tool_name,
                input,
                identity=identity,
            )
            if isinstance(result, dict) and "error" in result:
                return ToolResult(
                    success=False,
                    data=redact_tool_payload(result.get("data")),
                    error=result["error"],
                )
            return ToolResult(success=True, data=redact_tool_payload(result))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["input_schema"] = self._input_schema
        base["type"] = "mcp"
        return base
