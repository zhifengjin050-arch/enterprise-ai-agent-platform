"""Tool registry for Agent Runtime."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult
from app.core.exceptions import ToolNotFoundException, ToolPermissionException

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of available agent tools.

    Supports register / discover / execute.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        logger.info("Registered tool '%s'", tool.name)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tools.values()]

    def discover(self, keyword: str = "") -> List[str]:
        """Discover tool names, optionally filtered by keyword."""
        kw = keyword.lower().strip()
        names = []
        for name, tool in self._tools.items():
            blob = f"{name} {tool.description}".lower()
            if not kw or kw in blob:
                names.append(name)
        return names

    async def execute(
        self,
        name: str,
        input: Dict[str, Any],
        context: Optional[ToolContext] = None,
        *,
        allowed_permissions: Optional[List[str]] = None,
    ) -> ToolResult:
        """Execute a registered tool by name.

        Args:
            name: Tool name.
            input: Tool input.
            context: Optional execution context.
            allowed_permissions: If set, tool.permissions must be subset.

        Returns:
            ToolResult.

        Raises:
            ToolNotFoundException: Unknown tool.
            ToolPermissionException: Missing permission.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundException(
                message=f"Tool '{name}' not found",
                details={"tool": name, "available": list(self._tools.keys())},
            )

        if allowed_permissions is not None and tool.permissions:
            missing = [p for p in tool.permissions if p not in allowed_permissions]
            if missing:
                raise ToolPermissionException(
                    message=f"Missing permissions for tool '{name}'",
                    details={"tool": name, "missing": missing},
                )

        ctx = context or ToolContext()
        logger.info("Executing tool '%s' task=%s", name, ctx.task_id)
        return await tool.execute(input, ctx)


def build_default_registry() -> ToolRegistry:
    """Build a registry with built-in knowledge tools."""
    from app.agent_runtime.tools.connector_sync import ConnectorSyncTool
    from app.agent_runtime.tools.document_query import DocumentQueryTool
    from app.agent_runtime.tools.graph_query import GraphQueryTool
    from app.agent_runtime.tools.knowledge_search import KnowledgeSearchTool

    registry = ToolRegistry()
    for tool in (
        KnowledgeSearchTool(),
        GraphQueryTool(),
        DocumentQueryTool(),
        ConnectorSyncTool(),
    ):
        registry.register(tool)
    return registry


# Module singleton (lazy)
_default_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry
