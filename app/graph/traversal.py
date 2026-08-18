"""Graph traversal utilities.

Provides basic path-finding between entities in the knowledge graph
using BFS (breadth-first search) over PostgreSQL-stored relations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.entity.repository import EntityRepository
from app.relation.repository import RelationRepository


class GraphTraversal:
    """Graph traversal for entity relation path-finding.

    Uses BFS to find paths between entities without requiring
    a dedicated graph database.
    """

    async def find_path(
        self,
        source: str,
        target: str,
        session=None,
        entity_repo: Optional[EntityRepository] = None,
        relation_repo: Optional[RelationRepository] = None,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """Find a path from source to target entity by name.

        Args:
            source: Source entity name.
            target: Target entity name.
            session: AsyncSession.
            entity_repo: Optional EntityRepository override.
            relation_repo: Optional RelationRepository override.
            max_depth: Maximum graph traversal depth.

        Returns:
            Dict with 'found' (bool), 'path' (list of step dicts).
        """
        if session is None:
            return {"found": False, "path": []}

        repo_entity = entity_repo or EntityRepository(session)
        repo_relation = relation_repo or RelationRepository(session)

        # Resolve names to UUIDs
        source_entities = await repo_entity.find_by_name(source, exact=True)
        target_entities = await repo_entity.find_by_name(target, exact=True)

        if not source_entities or not target_entities:
            return {"found": False, "path": []}

        source_id = str(source_entities[0].id)
        target_id = str(target_entities[0].id)
        source_name = source_entities[0].name
        target_name = target_entities[0].name

        # BFS
        visited: Set[str] = {source_id}
        queue: List[tuple] = [(source_id, 0, [source_name])]

        while queue:
            current_id, depth, path_so_far = queue.pop(0)
            if depth >= max_depth:
                continue

            # Fetch neighbors of current entity
            graph = await repo_relation.get_entity_graph(current_id)
            for rel in graph.get("relations", []):
                neighbor_id = None
                neighbor_name = None

                if str(rel.source_entity_id) == current_id:
                    neighbor_id = str(rel.target_entity_id)
                elif str(rel.target_entity_id) == current_id:
                    neighbor_id = str(rel.source_entity_id)

                if neighbor_id and neighbor_id not in visited:
                    visited.add(neighbor_id)

                    # Get neighbor name
                    n_entity = graph.get("neighbors", {}).get(neighbor_id)
                    if n_entity:
                        neighbor_name = n_entity.name
                    else:
                        neighbor_n = await repo_entity.get_entity(neighbor_id)
                        neighbor_name = neighbor_n.name if neighbor_n else "?"

                    new_path = path_so_far + [neighbor_name]

                    if neighbor_id == target_id:
                        return {
                            "found": True,
                            "path": new_path,
                            "source_name": source_name,
                            "target_name": target_name,
                        }

                    queue.append((neighbor_id, depth + 1, new_path))

        return {
            "found": False,
            "path": [source_name, f"...(no path within depth {max_depth})...", target_name],
            "source_name": source_name,
            "target_name": target_name,
        }


async def find_path_between(
    source: str,
    target: str,
    session=None,
    max_depth: int = 5,
) -> Dict[str, Any]:
    """Convenience function for path finding.

    Args:
        source: Source entity name.
        target: Target entity name.
        session: AsyncSession.
        max_depth: Max traversal depth.

    Returns:
        Dict with 'found' and 'path'.
    """
    traversal = GraphTraversal()
    return await traversal.find_path(
        source=source,
        target=target,
        session=session,
        max_depth=max_depth,
    )
