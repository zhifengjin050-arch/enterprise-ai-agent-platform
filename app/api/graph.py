"""Knowledge Graph API endpoints.

Provides entity lookup, neighbor queries, and path-finding
over the PostgreSQL-backed knowledge graph (Knowledge Graph Lite).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.db.session import get_session_factory
from app.graph.query import GraphQueryService
from app.graph.traversal import find_path_between

router = APIRouter(prefix="/api/graph", tags=["Graph"])


def _get_session():
    """Create a new async session for graph operations."""
    factory = get_session_factory()
    return factory()


@router.get("/entity/{name}")
async def get_entity(name: str) -> Dict[str, Any]:
    """Look up an entity by name.

    Args:
        name: Entity name (e.g., "Redis", "订单服务").

    Returns:
        Entity info with relations.
    """
    service = GraphQueryService()
    factory = get_session_factory()
    async with factory() as session:
        result = await service.get_entity(name, session=session)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Entity '{name}' not found",
            )
        # Also fetch relations
        from app.entity.repository import EntityRepository
        from app.relation.repository import RelationRepository
        entity_repo = EntityRepository(session)
        relation_repo = RelationRepository(session)
        entities = await entity_repo.find_by_name(name, exact=True)
        if entities:
            graph = await relation_repo.get_entity_graph(str(entities[0].id))
            relations = []
            for rel in graph.get("relations", []):
                src_name = entities[0].name
                tgt_id = str(rel.target_entity_id)
                tgt_entity = await entity_repo.get_entity(tgt_id)
                tgt_name = tgt_entity.name if tgt_entity else tgt_id
                relations.append({
                    "source": src_name,
                    "target": tgt_name,
                    "type": rel.relation_type.value if hasattr(rel.relation_type, "value") else str(rel.relation_type),
                    "confidence": rel.confidence,
                })
            result["relations"] = relations
        return result


@router.get("/entity/{name}/neighbors")
async def get_entity_neighbors(name: str) -> Dict[str, Any]:
    """Get an entity and its one-hop neighbors.

    Args:
        name: Entity name.

    Returns:
        Entity with neighbors list.
    """
    service = GraphQueryService()
    factory = get_session_factory()
    async with factory() as session:
        result = await service.get_neighbors(name, session=session)
        if result.get("entity") is None:
            raise HTTPException(
                status_code=404,
                detail=f"Entity '{name}' not found",
            )
        return result


@router.get("/path")
async def find_path(
    source: str = Query(..., description="Source entity name"),
    target: str = Query(..., description="Target entity name"),
    max_depth: int = Query(5, ge=1, le=10),
) -> Dict[str, Any]:
    """Find a path between two entities.

    Args:
        source: Source entity name.
        target: Target entity name.
        max_depth: Maximum traversal depth.

    Returns:
        Path result with 'found' and 'path' list.
    """
    factory = get_session_factory()
    async with factory() as session:
        result = await find_path_between(
            source=source,
            target=target,
            session=session,
            max_depth=max_depth,
        )
        return result


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Fuzzy search entities by name keyword.

    Args:
        q: Search keyword.
        limit: Max results.

    Returns:
        List of matching entity dicts.
    """
    service = GraphQueryService()
    factory = get_session_factory()
    async with factory() as session:
        results = await service.search_entities(q, session=session, limit=limit)
        return results
