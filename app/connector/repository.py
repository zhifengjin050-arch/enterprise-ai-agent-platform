"""Connector repository — CRUD for ConnectorConfig and SyncRecord.

Enforces the repository pattern: no direct ORM access from service/API layers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.models import ConnectorConfig, SyncRecord, SyncStatus


class ConnectorConfigRepository:
    """Repository for ConnectorConfig CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: Optional[str] = None,
        name: str,
        connector_type: str,
        config_json: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> ConnectorConfig:
        """Create a new connector configuration.

        Args:
            tenant_id: Tenant isolation key.
            name: Human-readable name.
            connector_type: Type key (feishu, yuque, gitlab, etc.).
            config_json: Connector-specific settings.
            enabled: Whether the connector is active.

        Returns:
            The created ConnectorConfig.
        """
        record = ConnectorConfig(
            tenant_id=tenant_id,
            name=name,
            type=connector_type,
            config_json=config_json or {},
            enabled=enabled,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get(self, connector_id: str) -> Optional[ConnectorConfig]:
        """Get a connector config by ID.

        Args:
            connector_id: UUID string.

        Returns:
            ConnectorConfig or None.
        """
        stmt = select(ConnectorConfig).where(ConnectorConfig.id == connector_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        tenant_id: Optional[str] = None,
        connector_type: Optional[str] = None,
        enabled_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConnectorConfig]:
        """List connector configs with optional filters.

        Args:
            tenant_id: Filter by tenant.
            connector_type: Filter by type.
            enabled_only: Only return enabled connectors.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of ConnectorConfig.
        """
        stmt = select(ConnectorConfig).order_by(ConnectorConfig.created_at.desc())
        from app.tenant.isolation import apply_tenant_filter

        stmt = apply_tenant_filter(stmt, ConnectorConfig.tenant_id, tenant_id)
        if connector_type is not None:
            stmt = stmt.where(ConnectorConfig.type == connector_type)
        if enabled_only:
            stmt = stmt.where(ConnectorConfig.enabled == True)  # noqa: E712
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        connector_id: str,
        *,
        name: Optional[str] = None,
        config_json: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[ConnectorConfig]:
        """Update a connector config.

        Args:
            connector_id: UUID string.
            name: New name.
            config_json: New config JSON.
            enabled: New enabled state.

        Returns:
            Updated ConnectorConfig or None.
        """
        record = await self.get(connector_id)
        if record is None:
            return None
        if name is not None:
            record.name = name
        if config_json is not None:
            record.config_json = config_json
        if enabled is not None:
            record.enabled = enabled
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def delete(self, connector_id: str) -> bool:
        """Delete a connector config.

        Args:
            connector_id: UUID string.

        Returns:
            True if deleted, False if not found.
        """
        record = await self.get(connector_id)
        if record is None:
            return False
        await self._session.delete(record)
        await self._session.flush()
        return True

    async def update_last_sync(
        self, connector_id: str, timestamp: Optional[datetime] = None
    ) -> None:
        """Update the last_sync_at timestamp.

        Args:
            connector_id: UUID string.
            timestamp: Sync timestamp (defaults to now).
        """
        ts = timestamp or datetime.now(timezone.utc)
        stmt = (
            update(ConnectorConfig)
            .where(ConnectorConfig.id == connector_id)
            .values(last_sync_at=ts)
        )
        await self._session.execute(stmt)


class SyncRecordRepository:
    """Repository for SyncRecord CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        connector_id: str,
        document_id: Optional[str] = None,
        status: str = SyncStatus.PENDING.value,
    ) -> SyncRecord:
        """Create a new sync record.

        Args:
            connector_id: FK to ConnectorConfig.
            document_id: Optional external document ID.
            status: Initial status.

        Returns:
            The created SyncRecord.
        """
        record = SyncRecord(
            connector_id=connector_id,
            document_id=document_id,
            status=status,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get(self, record_id: str) -> Optional[SyncRecord]:
        """Get a sync record by ID.

        Args:
            record_id: UUID string.

        Returns:
            SyncRecord or None.
        """
        stmt = select(SyncRecord).where(SyncRecord.id == record_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_connector(
        self,
        connector_id: str,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> List[SyncRecord]:
        """List sync records for a connector.

        Args:
            connector_id: FK to ConnectorConfig.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of SyncRecord sorted by started_at desc.
        """
        stmt = (
            select(SyncRecord)
            .where(SyncRecord.connector_id == connector_id)
            .order_by(SyncRecord.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        record_id: str,
        *,
        status: str,
        error: Optional[str] = None,
        documents_count: Optional[int] = None,
    ) -> Optional[SyncRecord]:
        """Update a sync record's status and result.

        Args:
            record_id: UUID string.
            status: New status.
            error: Optional error message.
            documents_count: Number of synced documents.

        Returns:
            Updated SyncRecord or None.
        """
        record = await self.get(record_id)
        if record is None:
            return None
        record.status = status
        if error is not None:
            record.error = error
        if documents_count is not None:
            record.documents_count = documents_count
        if status in (SyncStatus.SUCCESS.value, SyncStatus.FAILED.value):
            record.finished_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(record)
        return record
