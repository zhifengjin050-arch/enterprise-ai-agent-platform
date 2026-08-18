"""Sync worker — background execution of SyncJobs.

Provides SyncWorker that can run jobs asynchronously without blocking
the API request path.  Jobs are created as PENDING and then executed
in a background asyncio task.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from app.db.session import get_session_factory
from app.sync_engine.sync_engine import SyncEngine

logger = logging.getLogger(__name__)


class SyncWorker:
    """Background worker for executing SyncJobs.

    Tracks active jobs to prevent duplicate concurrent execution
    of the same connector.
    """

    def __init__(self) -> None:
        self._active: Set[str] = set()  # connector_ids currently syncing

    @property
    def active_connectors(self) -> Set[str]:
        """Set of connector IDs currently being synced."""
        return set(self._active)

    def is_active(self, connector_id: str) -> bool:
        """Check if a connector is currently being synced."""
        return connector_id in self._active

    async def submit(
        self,
        *,
        connector_id: str,
        connector_type: str,
        config: Optional[Dict[str, Any]] = None,
        sync_mode: str = "full",
        tenant_id: Optional[str] = None,
        resume: bool = True,
    ) -> str:
        """Submit a sync job for background execution.

        Creates the SyncJob immediately (PENDING), then schedules
        background execution.  Returns the job ID right away.

        Args:
            connector_id: Connector config UUID.
            connector_type: Registered connector type.
            config: Connector configuration.
            sync_mode: full | incremental | delta.
            tenant_id: Optional tenant key.
            resume: Whether to resume from checkpoint.

        Returns:
            The SyncJob ID.

        Raises:
            RuntimeError: If the connector is already syncing.
        """
        if connector_id in self._active:
            raise RuntimeError(
                f"Connector '{connector_id}' already has an active sync"
            )

        # Create job in a short-lived session
        factory = get_session_factory()
        async with factory() as session:
            engine = SyncEngine(session)
            cursor = None
            if sync_mode == "incremental" and resume:
                cursor = await engine.checkpoints.get(connector_id)

            job = await engine.jobs.create_job(
                connector_id=connector_id,
                sync_mode=sync_mode,
                tenant_id=tenant_id,
                cursor=cursor,
            )
            await session.commit()
            job_id = job.id

        # Schedule background execution
        self._active.add(connector_id)
        asyncio.create_task(
            self._run(
                job_id=job_id,
                connector_id=connector_id,
                connector_type=connector_type,
                config=config or {},
            )
        )
        logger.info(
            "SyncWorker submitted job %s for connector %s (mode=%s)",
            job_id,
            connector_id,
            sync_mode,
        )
        return job_id

    async def _run(
        self,
        *,
        job_id: str,
        connector_id: str,
        connector_type: str,
        config: Dict[str, Any],
    ) -> None:
        """Execute a SyncJob in the background.

        Args:
            job_id: SyncJob UUID.
            connector_id: Connector UUID (for active tracking).
            connector_type: Connector type key.
            config: Connector configuration.
        """
        try:
            factory = get_session_factory()
            async with factory() as session:
                engine = SyncEngine(session)
                await engine.execute_job(
                    job_id,
                    connector_type=connector_type,
                    config=config,
                )
        except Exception as exc:
            logger.error(
                "SyncWorker background execution failed for job %s: %s",
                job_id,
                exc,
            )
        finally:
            self._active.discard(connector_id)


# Module-level singleton
sync_worker = SyncWorker()
