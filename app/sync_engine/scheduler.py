"""Sync Engine scheduler — periodic sync based on connector schedules.

Replaces (and is preferred over) the legacy app/connector/scheduler.py
for new code.  The legacy scheduler is kept for backward compatibility
and will be deprecated in a future phase.

This scheduler:
    1. Polls enabled connectors on an interval
    2. Checks if they are due based on schedule config
    3. Submits SyncJobs via SyncWorker
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.connector.models import ConnectorConfig
from app.connector.repository import ConnectorConfigRepository
from app.db.session import get_session_factory
from app.sync_engine.worker import sync_worker

logger = logging.getLogger(__name__)


class SyncEngineScheduler:
    """Async scheduler that triggers SyncJobs for due connectors.

    Args:
        poll_interval: Seconds between polls (default 60).
    """

    def __init__(self, poll_interval: int = 60) -> None:
        self._poll_interval = poll_interval
        self._running = False

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        logger.info(
            "SyncEngineScheduler started (poll_interval=%ds)",
            self._poll_interval,
        )
        while self._running:
            try:
                await self._check_and_sync()
            except Exception as exc:
                logger.error("SyncEngineScheduler error: %s", exc)
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("SyncEngineScheduler stopped")

    async def _check_and_sync(self) -> None:
        """Check all enabled connectors and submit jobs if due."""
        factory = get_session_factory()
        async with factory() as session:
            repo = ConnectorConfigRepository(session)
            connectors = await repo.list(enabled_only=True)

        for connector in connectors:
            if sync_worker.is_active(connector.id):
                continue
            if not self._is_due(connector):
                continue

            sync_mode = (connector.config_json or {}).get("sync_mode", "full")
            try:
                job_id = await sync_worker.submit(
                    connector_id=connector.id,
                    connector_type=connector.type,
                    config=connector.config_json or {},
                    sync_mode=sync_mode,
                    tenant_id=connector.tenant_id,
                )
                logger.info(
                    "Scheduled SyncJob %s for connector %s (%s)",
                    job_id,
                    connector.name,
                    connector.type,
                )
            except RuntimeError:
                # Already active — skip
                pass
            except Exception as exc:
                logger.error(
                    "Failed to submit sync for connector %s: %s",
                    connector.id,
                    exc,
                )

    @staticmethod
    def _is_due(connector: ConnectorConfig) -> bool:
        """Check if a connector is due for sync based on schedule config.

        Args:
            connector: The connector config.

        Returns:
            True if due for sync.
        """
        config = connector.config_json or {}
        last_sync = connector.last_sync_at

        if last_sync is None:
            return True

        now = datetime.now(timezone.utc)
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)

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

        return (now - last_sync) > timedelta(hours=1)


# Module-level singleton
sync_engine_scheduler = SyncEngineScheduler()
