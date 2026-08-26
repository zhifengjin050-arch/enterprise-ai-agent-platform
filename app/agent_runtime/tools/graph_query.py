"""GraphQueryTool — wraps KnowledgeGraph."""

from __future__ import annotations

from typing import Any, Dict

from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult


class GraphQueryTool(BaseTool):
    name = "graph_query"
    description = "Query the knowledge graph for an entity subgraph"
    permissions = ["knowledge.read"]

    async def execute(self, input: Dict[str, Any], context: ToolContext) -> ToolResult:
        entity_id = str(input.get("entity_id") or "").strip()
        entity_name = str(input.get("entity_name") or input.get("name") or "").strip()
        depth = int(input.get("depth") or 1)

        try:
            from app.knowledge.graph import KnowledgeGraph

            kg = KnowledgeGraph(context.session)

            if not entity_id and entity_name and context.session is not None:
                from app.entity.repository import EntityRepository

                repo = EntityRepository(context.session)
                entities = await repo.list_entities(limit=100)
                match = next(
                    (e for e in entities if e.name.lower() == entity_name.lower()),
                    None,
                )
                if match is None:
                    match = next(
                        (e for e in entities if entity_name.lower() in e.name.lower()),
                        None,
                    )
                if match is not None:
                    entity_id = str(match.id)

            if not entity_id:
                return ToolResult(
                    success=False,
                    error="entity_id or entity_name is required",
                )

            subgraph = await kg.get_subgraph(entity_id, depth=depth, session=context.session)
            return ToolResult(success=True, data=subgraph)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
