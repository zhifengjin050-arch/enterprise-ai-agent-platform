"""Tool base class for Agent Runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolContext:
    """Execution context passed to tools."""

    tenant_id: Optional[str] = None
    task_id: str = ""
    agent_id: str = ""
    session: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool = True
    data: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base class for Agent tools.

    Subclasses must set ``name`` / ``description`` and implement ``execute``.
    """

    name: str = "base_tool"
    description: str = ""
    permissions: list[str] = []

    @abstractmethod
    async def execute(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """Execute the tool.

        Args:
            input: Tool-specific input payload.
            context: Execution context.

        Returns:
            ToolResult.
        """
        ...

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permissions": list(self.permissions),
        }
