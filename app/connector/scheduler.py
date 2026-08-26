"""Scheduled synchronization for connector instances.

Runs periodic sync based on schedule intervals (hourly, daily, custom).
Tracks last_sync_at to avoid redundant syncs and supports manual trigger.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Set

from app.connector.models import ConnectorConfig, SyncStatus
from app.connector.registry import connector_registry
from app.connector.repository import ConnectorConfigRepository, SyncRecordRepository
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Async scheduler for periodic connector synchronization.

    Polls enabled connectors and triggers sync based on their
    configured schedule interval (hourly or daily).

    Args:
        poll_interval: Seconds between scheduler polls (default 60s).
    """

    def __init__(self, poll_interval: int = 60) -> None:
        self._poll_interval = poll_interval
        self._running = False
        self._active_syncs: Set[str] = set()

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        logger.info("SyncScheduler started (poll_interval=%ds)", self._poll_interval)
        while self._running:
            try:
                await self._check_and_sync()
            except Exception as exc:
                logger.error("SyncScheduler error: %s", exc)
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("SyncScheduler stopped")

    async def _check_and_sync(self) -> None:
        """Check all enabled connectors and trigger sync if due."""
        factory = get_session_factory()
        async with factory() as session:
            repo = ConnectorConfigRepository(session)
            connectors = await repo.list(enabled_only=True)

            for connector in connectors:
                if connector.id in self._active_syncs:
                    continue  # Already syncing

                if self._is_due(connector):
                    self._active_syncs.add(connector.id)

        # Trigger sync outside the session
        for connector in connectors:
            if connector.id in self._active_syncs:
                if self._is_due(connector):
                    asyncio.create_task(self._run_sync(connector))

    async def trigger_sync(self, connector_id: str) -> None:
        """Manually trigger a sync for a specific connector.

        Args:
            connector_id: UUID string of the connector config.
        """
        if connector_id in self._active_syncs:
            logger.warning("Sync already in progress for connector %s", connector_id)
            return

        factory = get_session_factory()
        async with factory() as session:
            repo = ConnectorConfigRepository(session)
            connector = await repo.get(connector_id)
            if connector is None or not connector.enabled:
                logger.warning("Connector %s not found or disabled", connector_id)
                return

        self._active_syncs.add(connector_id)
        asyncio.create_task(self._run_sync(connector))

    @staticmethod
    def _is_due(connector: ConnectorConfig) -> bool:
        """Check if a connector is due for sync based on config schedule.

        Args:
            connector: The connector config.

        Returns:
            True if due for sync.
        """
        config = connector.config_json or {}
        last_sync = connector.last_sync_at

        if last_sync is None:
            return True  # Never synced

        now = datetime.now(timezone.utc)

        # Ensure last_sync is timezone-aware (SQLite stores naive datetime)
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)

        # Check if a custom interval is configured first
        custom_minutes = config.get("schedule_interval_minutes")
        if custom_minutes is not None:
            return (now - last_sync) > timedelta(minutes=custom_minutes)

        schedule = config.get("schedule", "hourly")
        if schedule == "hourly":
            return (now - last_sync) > timedelta(hours=1)
        if schedule == "daily":
            return (now - last_sync) > timedelta(days=1)
        if schedule == "never":
            return False

        # Default hourly fallback
        return (now - last_sync) > timedelta(hours=1)

    async def _run_sync(self, connector: ConnectorConfig) -> ConnectorConfig:
        """Execute sync for a single connector.

        Args:
            connector: The connector config to sync.

        Returns:
            The updated connector config.
        """
        connector_id = connector.id
        logger.info("Starting sync for connector %s (%s)", connector.name, connector.type)

        factory = get_session_factory()
        # Create sync record
        async with factory() as session:
            sync_repo = SyncRecordRepository(session)
            record = await sync_repo.create(
                connector_id=connector_id,
                status=SyncStatus.RUNNING.value,
            )
            await session.commit()

        try:
            # Create connector instance and run sync
            if not connector_registry.is_registered(connector.type):
                raise ValueError(f"Connector type '{connector.type}' not registered")

            inst = connector_registry.create(connector.type, config=connector.config_json)
            sync_mode = (connector.config_json or {}).get("sync_mode", "full")
            cursor = (connector.config_json or {}).get("sync_cursor")
            raw_result = await inst.sync(sync_mode=sync_mode, cursor=cursor)

            # Normalize SyncResult | List[ConnectorDocument] for Phase 3/4 compat
            from app.connector.sync_modes import normalize_sync_result

            sync_result = normalize_sync_result(raw_result)
            documents = sync_result.documents

            # Import each document through the task queue
            from app.task.queue import TaskQueue

            queue = TaskQueue()
            imported_count = 0
            errors: list[str] = []

            for doc in documents:
                try:
                    async with factory() as session:
                        await queue.enqueue(
                            session,
                            task_type="connector_sync",
                            payload={
                                "title": doc.title,
                                "content": doc.content,
                                "metadata": {
                                    **(doc.metadata or {}),
                                    "connector_id": connector_id,
                                    "external_id": doc.id,
                                    "external_url": doc.url,
                                },
                            },
                        )
                        await session.commit()
                    imported_count += 1
                except Exception as exc:
                    errors.append(f"Failed to enqueue {doc.id}: {exc}")

            # Update sync record
            async with factory() as session:
                sync_repo = SyncRecordRepository(session)
                await sync_repo.update_status(
                    record.id,
                    status=SyncStatus.SUCCESS.value if not errors else SyncStatus.FAILED.value,
                    documents_count=imported_count,
                    error="; ".join(errors[:5]) if errors else None,
                )
                # Update last_sync_at
                config_repo = ConnectorConfigRepository(session)
                await config_repo.update_last_sync(connector_id)
                await session.commit()

            logger.info(
                "Sync completed for %s: %d documents imported, %d errors",
                connector.name,
                imported_count,
                len(errors),
            )

        except Exception as exc:
            logger.error("Sync failed for connector %s: %s", connector.name, exc)
            async with factory() as session:
                sync_repo = SyncRecordRepository(session)
                await sync_repo.update_status(
                    record.id,
                    status=SyncStatus.FAILED.value,
                    error=str(exc),
                )
                await session.commit()
        finally:
            self._active_syncs.discard(connector_id)

        return connector


# Module-level singleton
sync_scheduler = SyncScheduler()
