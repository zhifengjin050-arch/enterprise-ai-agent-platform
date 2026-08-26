"""Relation repository — database access layer for KnowledgeRelation.

All knowledge relation persistence goes through this repository.
API and workflow layers must not execute raw ORM queries directly.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entity.models import KnowledgeEntity
from app.relation.models import KnowledgeRelation, RelationType


def _as_uuid(value: Union[str, uuid.UUID]) -> uuid.UUID:
    """Normalize string/UUID input to UUID."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class RelationRepository:
    """Async repository for KnowledgeRelation CRUD operations.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_relation(
        self,
        *,
        source_entity_id: Union[str, uuid.UUID],
        target_entity_id: Union[str, uuid.UUID],
        relation_type: Union[str, RelationType] = RelationType.RELATED_TO,
        confidence: float = 1.0,
        source_document_id: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeRelation:
        """Create and persist a knowledge relation.

        Args:
            source_entity_id: Source entity UUID.
            target_entity_id: Target entity UUID.
            relation_type: Type of relation.
            confidence: Confidence score.
            source_document_id: Optional originating document ID.
            metadata_json: Optional metadata.

        Returns:
            Persisted KnowledgeRelation.
        """
        if isinstance(relation_type, str):
            relation_type = RelationType(relation_type)

        relation = KnowledgeRelation(
            source_entity_id=_as_uuid(source_entity_id),
            target_entity_id=_as_uuid(target_entity_id),
            relation_type=relation_type,
            confidence=confidence,
            source_document_id=source_document_id,
            metadata_json=metadata_json or {},
        )
        self.session.add(relation)
        await self.session.flush()
        await self.session.refresh(relation)
        return relation

    async def get_relations(
        self,
        entity_id: Union[str, uuid.UUID],
        *,
        direction: str = "both",
        relation_type: Optional[Union[str, RelationType]] = None,
        limit: int = 50,
    ) -> List[KnowledgeRelation]:
        """Get all relations involving an entity.

        Args:
            entity_id: Entity UUID.
            direction: 'outgoing', 'incoming', or 'both'.
            relation_type: Optional relation type filter.
            limit: Max results.

        Returns:
            List of KnowledgeRelation.
        """
        eid = _as_uuid(entity_id)
        stmt = select(KnowledgeRelation)

        if direction == "outgoing":
            stmt = stmt.where(KnowledgeRelation.source_entity_id == eid)
        elif direction == "incoming":
            stmt = stmt.where(KnowledgeRelation.target_entity_id == eid)
        else:
            stmt = stmt.where(
                or_(
                    KnowledgeRelation.source_entity_id == eid,
                    KnowledgeRelation.target_entity_id == eid,
                )
            )

        if relation_type is not None:
            if isinstance(relation_type, str):
                relation_type = RelationType(relation_type)
            stmt = stmt.where(KnowledgeRelation.relation_type == relation_type)

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_entity_graph(
        self,
        entity_id: Union[str, uuid.UUID],
        depth: int = 1,
    ) -> Dict[str, Any]:
        """Get the subgraph centered on an entity.

        Args:
            entity_id: Center entity UUID.
            depth: Traversal depth (currently only depth=1 supported).

        Returns:
            Dict with 'entity' and 'relations' keys.
        """
        eid = _as_uuid(entity_id)
        entity_stmt = select(KnowledgeEntity).where(KnowledgeEntity.id == eid)
        entity_result = await self.session.execute(entity_stmt)
        entity = entity_result.scalar_one_or_none()
        if entity is None:
            return {"entity": None, "relations": []}

        relations = await self.get_relations(eid, direction="both")

        # Collect neighbor entity IDs
        neighbor_ids: set = set()
        for r in relations:
            if r.source_entity_id == eid:
                neighbor_ids.add(r.target_entity_id)
            if r.target_entity_id == eid:
                neighbor_ids.add(r.source_entity_id)

        # Fetch neighbor entities
        if neighbor_ids:
            neighbor_stmt = select(KnowledgeEntity).where(KnowledgeEntity.id.in_(neighbor_ids))
            neighbor_result = await self.session.execute(neighbor_stmt)
            neighbors = {str(n.id): n for n in neighbor_result.scalars().all()}
        else:
            neighbors = {}

        return {
            "entity": entity,
            "relations": relations,
            "neighbors": neighbors,
        }

    async def delete_relation(
        self,
        relation_id: Union[str, uuid.UUID],
    ) -> bool:
        """Delete a relation by UUID.

        Args:
            relation_id: Relation UUID.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(KnowledgeRelation).where(KnowledgeRelation.id == _as_uuid(relation_id))
        result = await self.session.execute(stmt)
        relation = result.scalar_one_or_none()
        if relation is None:
            return False
        await self.session.delete(relation)
        await self.session.flush()
        return True

    @staticmethod
    def to_dict(relation: KnowledgeRelation) -> Dict[str, Any]:
        """Serialize a relation to a JSON-friendly dict.

        Args:
            relation: KnowledgeRelation instance.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(relation.id),
            "source_entity_id": str(relation.source_entity_id),
            "target_entity_id": str(relation.target_entity_id),
            "relation_type": relation.relation_type.value
            if isinstance(relation.relation_type, RelationType)
            else str(relation.relation_type),
            "confidence": relation.confidence,
            "source_document_id": relation.source_document_id,
            "metadata_json": relation.metadata_json or {},
            "created_at": relation.created_at.isoformat() if relation.created_at else None,
        }

    @staticmethod
    def relation_to_dict_with_names(
        relation: KnowledgeRelation,
        source_name: str = "",
        target_name: str = "",
    ) -> Dict[str, Any]:
        """Serialize a relation including entity names.

        Args:
            relation: KnowledgeRelation instance.
            source_name: Source entity name.
            target_name: Target entity name.

        Returns:
            Dict with names included.
        """
        d = RelationRepository.to_dict(relation)
        d["source_name"] = source_name
        d["target_name"] = target_name
        return d
