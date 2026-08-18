"""DocumentQueryTool — fetch a knowledge document by ID."""

from __future__ import annotations

from typing import Any, Dict

from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult


class DocumentQueryTool(BaseTool):
    name = "document_query"
    description = "Fetch a knowledge document by ID"
    permissions = ["knowledge.read"]

    async def execute(self, input: Dict[str, Any], context: ToolContext) -> ToolResult:
        document_id = str(input.get("document_id") or input.get("id") or "").strip()
        if not document_id:
            return ToolResult(success=False, error="document_id is required")
        if context.session is None:
            return ToolResult(success=False, error="database session required")

        try:
            from app.knowledge.repository import KnowledgeRepository

            repo = KnowledgeRepository(context.session)
            doc = await repo.get_document(document_id)
            if doc is None:
                return ToolResult(success=False, error=f"Document '{document_id}' not found")
            return ToolResult(
                success=True,
                data=KnowledgeRepository.to_dict(doc),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
