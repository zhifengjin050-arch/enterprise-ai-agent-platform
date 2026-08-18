"""Entity repository — database access layer for KnowledgeEntity.

All knowledge entity persistence goes through this repository.
API and workflow layers must not execute raw ORM queries directly.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entity.models import EntityType, KnowledgeEntity


def _as_uuid(value: Union[str, uuid.UUID]) -> uuid.UUID:
    """Normalize string/UUID input to UUID."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class EntityRepository:
    """Async repository for KnowledgeEntity CRUD operations.

    Args:
        session: Async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_entity(
        self,
        *,
        name: str,
        entity_type: Union[str, EntityType] = EntityType.COMPONENT,
        description: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        entity_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> KnowledgeEntity:
        """Create and persist a knowledge entity.

        Args:
            name: Entity name.
            entity_type: Entity type classification.
            description: Optional description.
            metadata_json: Optional metadata dict.
            entity_id: Optional explicit UUID.

        Returns:
            Persisted KnowledgeEntity.
        """
        if isinstance(entity_type, str):
            entity_type = EntityType(entity_type)

        entity = KnowledgeEntity(
            id=_as_uuid(entity_id) if entity_id else uuid.uuid4(),
            name=name,
            entity_type=entity_type,
            description=description,
            metadata_json=metadata_json or {},
        )
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_entity(
        self,
        entity_id: Union[str, uuid.UUID],
    ) -> Optional[KnowledgeEntity]:
        """Fetch an entity by UUID.

        Args:
            entity_id: Entity UUID.

        Returns:
            KnowledgeEntity or None.
        """
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.id == _as_uuid(entity_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name(
        self,
        name: str,
        *,
        exact: bool = True,
        limit: int = 10,
    ) -> List[KnowledgeEntity]:
        """Find entities by name.

        Args:
            name: Entity name to search for.
            exact: If True, exact match; otherwise ILIKE.
            limit: Max results.

        Returns:
            List of matching KnowledgeEntity.
        """
        if exact:
            stmt = (
                select(KnowledgeEntity)
                .where(KnowledgeEntity.name == name)
                .limit(limit)
            )
        else:
            stmt = (
                select(KnowledgeEntity)
                .where(KnowledgeEntity.name.ilike(f"%{name}%"))
                .limit(limit)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_entities(
        self,
        *,
        entity_type: Optional[Union[str, EntityType]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KnowledgeEntity]:
        """List entities with optional type filter.

        Args:
            entity_type: Optional entity type filter.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of KnowledgeEntity.
        """
        stmt = select(KnowledgeEntity)
        if entity_type is not None:
            if isinstance(entity_type, str):
                entity_type = EntityType(entity_type)
            stmt = stmt.where(KnowledgeEntity.entity_type == entity_type)
        stmt = (
            stmt.order_by(KnowledgeEntity.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_entity(
        self,
        entity_id: Union[str, uuid.UUID],
    ) -> bool:
        """Delete an entity by UUID.

        Args:
            entity_id: Entity UUID.

        Returns:
            True if deleted, False if not found.
        """
        entity = await self.get_entity(entity_id)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True

    @staticmethod
    def to_dict(entity: KnowledgeEntity) -> Dict[str, Any]:
        """Serialize an entity to a JSON-friendly dict.

        Args:
            entity: KnowledgeEntity instance.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(entity.id),
            "name": entity.name,
            "entity_type": entity.entity_type.value
            if isinstance(entity.entity_type, EntityType)
            else str(entity.entity_type),
            "description": entity.description,
            "metadata_json": entity.metadata_json or {},
            "created_at": entity.created_at.isoformat()
            if entity.created_at
            else None,
            "updated_at": entity.updated_at.isoformat()
            if entity.updated_at
            else None,
        }
