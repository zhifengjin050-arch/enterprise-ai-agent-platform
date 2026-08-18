"""Checkpoint store for incremental sync resume.

Provides SyncCheckpointManager for reading and writing durable cursors
so that failed syncs can resume from the last successful position.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.sync_engine.models import SyncCheckpoint

logger = logging.getLogger(__name__)


class SyncCheckpointManager:
    """Manages persistent sync cursors per connector.

    One checkpoint per connector_id.  On sync failure the last known
    good cursor is preserved so the next run can resume.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, connector_id: str) -> Optional[str]:
        """Get the current cursor for a connector.

        Args:
            connector_id: Connector config UUID.

        Returns:
            Cursor string, or None if no checkpoint exists.
        """
        stmt = select(SyncCheckpoint).where(
            SyncCheckpoint.connector_id == connector_id
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.cursor if record else None

    async def get_checkpoint(self, connector_id: str) -> Optional[SyncCheckpoint]:
        """Get the full checkpoint record for a connector.

        Args:
            connector_id: Connector config UUID.

        Returns:
            SyncCheckpoint or None.
        """
        stmt = select(SyncCheckpoint).where(
            SyncCheckpoint.connector_id == connector_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(
        self,
        connector_id: str,
        cursor: str,
        *,
        sync_job_id: Optional[str] = None,
    ) -> SyncCheckpoint:
        """Upsert a checkpoint cursor for a connector.

        Args:
            connector_id: Connector config UUID.
            cursor: New cursor value.
            sync_job_id: Optional SyncJob that produced this cursor.

        Returns:
            The upserted SyncCheckpoint.
        """
        existing = await self.get_checkpoint(connector_id)
        now = datetime.now(timezone.utc)

        if existing is not None:
            existing.cursor = cursor
            existing.updated_at = now
            if sync_job_id is not None:
                existing.sync_job_id = sync_job_id
            await self._session.flush()
            await self._session.refresh(existing)
            logger.info(
                "Checkpoint updated for connector %s: cursor=%s",
                connector_id,
                cursor[:80] if len(cursor) > 80 else cursor,
            )
            return existing

        record = SyncCheckpoint(
            connector_id=connector_id,
            cursor=cursor,
            sync_job_id=sync_job_id,
            updated_at=now,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        logger.info(
            "Checkpoint created for connector %s: cursor=%s",
            connector_id,
            cursor[:80] if len(cursor) > 80 else cursor,
        )
        return record

    async def clear(self, connector_id: str) -> bool:
        """Delete the checkpoint for a connector (e.g. after FULL sync).

        Args:
            connector_id: Connector config UUID.

        Returns:
            True if a checkpoint was deleted.
        """
        existing = await self.get_checkpoint(connector_id)
        if existing is None:
            return False
        await self._session.delete(existing)
        await self._session.flush()
        logger.info("Checkpoint cleared for connector %s", connector_id)
        return True
