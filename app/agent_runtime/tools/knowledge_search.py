"""KnowledgeSearchTool — wraps KnowledgeRetriever."""

from __future__ import annotations

from typing import Any, Dict

from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult


class KnowledgeSearchTool(BaseTool):
    name = "knowledge_search"
    description = "Hybrid search over the enterprise knowledge base (vector + BM25 + graph)"
    permissions = ["knowledge.read"]

    async def execute(self, input: Dict[str, Any], context: ToolContext) -> ToolResult:
        query = str(input.get("query") or input.get("q") or "").strip()
        if not query:
            return ToolResult(success=False, error="query is required")

        top_n = int(input.get("top_n") or 5)
        try:
            from app.knowledge.retrieval import KnowledgeRetriever

            retriever = KnowledgeRetriever(top_n=top_n)
            principal = {
                "tenant_id": context.tenant_id,
                "user_id": getattr(context, "user_id", None),
                "organization_id": getattr(context, "organization_id", None),
                "roles": getattr(context, "roles", None) or [],
            }
            results = await retriever.retrieve(
                query,
                top_n=top_n,
                use_graph=bool(input.get("use_graph", True)),
                use_rerank=bool(input.get("use_rerank", True)),
                session=context.session,
                principal=principal,
            )
            data = [r.to_dict() for r in results]
            return ToolResult(success=True, data=data, metadata={"count": len(data)})
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
