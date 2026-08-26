"""Graph query service.

Provides entity lookup, neighbor queries, and relation traversal
over the knowledge graph stored in PostgreSQL.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.entity.repository import EntityRepository
from app.relation.repository import RelationRepository


class GraphQueryService:
    """Query service for the knowledge graph (PostgreSQL-backed).

    Args:
        entity_repo: Optional EntityRepository override.
        relation_repo: Optional RelationRepository override.
    """

    def __init__(
        self,
        entity_repo: Optional[EntityRepository] = None,
        relation_repo: Optional[RelationRepository] = None,
    ):
        self._entity_repo = entity_repo
        self._relation_repo = relation_repo

    async def get_entity(
        self,
        name: str,
        session=None,
    ) -> Optional[Dict[str, Any]]:
        """Look up an entity by name.

        Args:
            name: Entity name.
            session: AsyncSession for repository access.

        Returns:
            Entity dict or None.
        """
        if session is None:
            return None
        repo = self._entity_repo or EntityRepository(session)
        entities = await repo.find_by_name(name, exact=True)
        if not entities:
            return None
        entity = entities[0]
        return EntityRepository.to_dict(entity)

    async def get_neighbors(
        self,
        name: str,
        session=None,
    ) -> Dict[str, Any]:
        """Get an entity and its direct (one-hop) neighbors.

        Args:
            name: Entity name.
            session: AsyncSession for repository access.

        Returns:
            Dict with 'entity' and 'neighbors' (list of entity names).
        """
        if session is None:
            return {"entity": None, "neighbors": []}

        repo_entity = self._entity_repo or EntityRepository(session)
        entities = await repo_entity.find_by_name(name, exact=True)
        if not entities:
            return {"entity": None, "neighbors": []}

        entity = entities[0]
        repo_relation = self._relation_repo or RelationRepository(session)
        graph = await repo_relation.get_entity_graph(str(entity.id))

        neighbor_names: List[str] = []
        for n in graph.get("neighbors", {}).values():
            if hasattr(n, "name"):
                neighbor_names.append(n.name)

        return {
            "entity": EntityRepository.to_dict(entity),
            "neighbors": sorted(neighbor_names),
        }

    async def find_path(
        self,
        source: str,
        target: str,
        session=None,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """Find a path between two entities by name.

        Args:
            source: Source entity name.
            target: Target entity name.
            session: AsyncSession for repository access.
            max_depth: Maximum traversal depth.

        Returns:
            Dict with 'found' (bool), 'path' (list of steps).
        """
        if session is None:
            return {"found": False, "path": []}

        from app.graph.traversal import GraphTraversal

        traversal = GraphTraversal()
        return await traversal.find_path(
            source=source,
            target=target,
            session=session,
            entity_repo=self._entity_repo,
            relation_repo=self._relation_repo,
            max_depth=max_depth,
        )

    async def search_entities(
        self,
        keyword: str,
        session=None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fuzzy search entities by name keyword.

        Args:
            keyword: Search keyword.
            session: AsyncSession.
            limit: Max results.

        Returns:
            List of entity dicts.
        """
        if session is None:
            return []
        repo = self._entity_repo or EntityRepository(session)
        entities = await repo.find_by_name(keyword, exact=False, limit=limit)
        return [EntityRepository.to_dict(e) for e in entities]
