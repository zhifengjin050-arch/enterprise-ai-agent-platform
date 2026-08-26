"""Knowledge Graph adapters for the Intelligence Layer.

Wraps existing app.entity / app.relation / app.graph infrastructure and
exposes GraphNode / GraphEdge dataclasses plus a high-level KnowledgeGraph
facade used by retrieval and APIs.

Entity types for Phase 5:
    Person, Organization, Project, System, API, Technology
(mapped onto / extending app.entity.models.EntityType)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.entity.models import EntityType, KnowledgeEntity
from app.graph.builder import GraphBuilder
from app.relation.models import KnowledgeRelation

logger = logging.getLogger(__name__)


# Phase 5 intelligence entity labels → existing EntityType values
INTELLIGENCE_ENTITY_MAP: Dict[str, str] = {
    "person": EntityType.PERSON.value,
    "organization": "organization",  # extended
    "project": "project",  # extended
    "system": EntityType.SERVICE.value,
    "api": "api",  # extended
    "technology": EntityType.TECHNOLOGY.value,
}


@dataclass
class GraphNode:
    """A node in the knowledge graph (entity adapter)."""

    id: str
    name: str
    entity_type: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_entity(cls, entity: KnowledgeEntity) -> GraphNode:
        et = entity.entity_type
        et_val = et.value if isinstance(et, EntityType) else str(et)
        return cls(
            id=str(entity.id),
            name=entity.name,
            entity_type=et_val,
            description=entity.description or "",
            metadata=entity.metadata_json or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdge:
    """An edge in the knowledge graph (relation adapter)."""

    id: str
    source_id: str
    target_id: str
    relation_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_relation(cls, relation: KnowledgeRelation) -> GraphEdge:
        rt = relation.relation_type
        rt_val = rt.value if hasattr(rt, "value") else str(rt)
        return cls(
            id=str(relation.id),
            source_id=str(relation.source_entity_id),
            target_id=str(relation.target_entity_id),
            relation_type=rt_val,
            metadata=relation.metadata_json or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "metadata": self.metadata,
        }


class KnowledgeGraph:
    """High-level knowledge graph facade for the Intelligence Layer.

    Builds graphs from documents and queries entities/relations.
    """

    def __init__(self, session: Any = None) -> None:
        self._session = session
        self._builder = GraphBuilder()

    async def build_from_document(
        self,
        title: str,
        content: str,
        *,
        document_id: Optional[str] = None,
        session: Any = None,
    ) -> Dict[str, Any]:
        """Extract entities/relations and persist via GraphBuilder.

        Returns:
            Dict with 'entities' and 'relations' (raw records).
        """
        sess = session or self._session
        result = await self._builder.build_from_document(
            title=title,
            content=content,
            session=sess,
            document_id=document_id,
        )
        return result

    async def get_entity(self, entity_id: str, session: Any = None) -> Optional[GraphNode]:
        """Get a single entity as GraphNode."""
        import uuid as _uuid

        from app.entity.repository import EntityRepository

        sess = session or self._session
        if sess is None:
            return None
        repo = EntityRepository(sess)
        try:
            eid = _uuid.UUID(entity_id)
        except ValueError:
            return None
        entity = await repo.get_entity(eid)
        if entity is None:
            return None
        return GraphNode.from_entity(entity)

    async def get_subgraph(
        self,
        entity_id: str,
        *,
        depth: int = 1,
        session: Any = None,
    ) -> Dict[str, Any]:
        """Get a subgraph centred on an entity.

        Returns:
            Dict with nodes (GraphNode[]) and edges (GraphEdge[]).
        """
        import uuid as _uuid

        from app.entity.repository import EntityRepository
        from app.relation.repository import RelationRepository

        sess = session or self._session
        if sess is None:
            return {"nodes": [], "edges": []}

        try:
            eid = _uuid.UUID(entity_id)
        except ValueError:
            return {"nodes": [], "edges": []}

        entity_repo = EntityRepository(sess)
        relation_repo = RelationRepository(sess)

        # Prefer repository helper when available
        graph_data = await relation_repo.get_entity_graph(eid, depth=depth)
        centre = graph_data.get("entity")
        if centre is None:
            centre = await entity_repo.get_entity(eid)
        if centre is None:
            return {"nodes": [], "edges": []}

        nodes: Dict[str, GraphNode] = {str(centre.id): GraphNode.from_entity(centre)}
        edges: List[GraphEdge] = []

        relations = graph_data.get("relations") or await relation_repo.get_relations(
            eid, direction="both"
        )
        neighbors = graph_data.get("neighbors") or {}

        for rel in relations:
            edges.append(GraphEdge.from_relation(rel))

        for nid, neighbour in neighbors.items():
            nodes[str(nid)] = GraphNode.from_entity(neighbour)

        # Ensure neighbour entities for edges are loaded
        for rel in relations:
            for neighbour_id in (rel.source_entity_id, rel.target_entity_id):
                nid = str(neighbour_id)
                if nid not in nodes:
                    neighbour = await entity_repo.get_entity(neighbour_id)
                    if neighbour is not None:
                        nodes[nid] = GraphNode.from_entity(neighbour)

        return {
            "entity_id": entity_id,
            "nodes": [n.to_dict() for n in nodes.values()],
            "edges": [e.to_dict() for e in edges],
            "depth": depth,
        }
