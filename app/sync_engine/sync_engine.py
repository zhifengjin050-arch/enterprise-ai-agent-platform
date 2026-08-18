"""Enterprise Sync Engine — core orchestration.

Orchestrates the full sync pipeline:

    Connector → SyncJob → SyncEngine → Checkpoint → SyncEvent → DocumentPipeline

Responsibilities:
    - Create and manage SyncJob lifecycle
    - Load / save checkpoints for incremental resume
    - Call Connector.sync(cursor) → SyncResult
    - Emit SyncEvents (CREATE / UPDATE / DELETE)
    - Enqueue documents into the DocumentPipeline via TaskQueue
    - Persist progress and handle failures with cursor preservation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.base import ConnectorDocument
from app.connector.registry import connector_registry
from app.connector.sync_modes import SyncMode, normalize_sync_result
from app.core.exceptions import ConnectorException, ConnectorSyncException
from app.sync_engine.checkpoint import SyncCheckpointManager
from app.sync_engine.events import SyncEvent, SyncEventType
from app.sync_engine.job_manager import SyncJobManager
from app.sync_engine.models import SyncJob

logger = logging.getLogger(__name__)


class SyncEngine:
    """Enterprise synchronisation engine.

    Executes a SyncJob end-to-end: load checkpoint → call connector →
    emit events → enqueue documents → save checkpoint → update job status.

    Args:
        session: Async SQLAlchemy session for persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._jobs = SyncJobManager(session)
        self._checkpoints = SyncCheckpointManager(session)

    @property
    def jobs(self) -> SyncJobManager:
        """Access the underlying SyncJobManager."""
        return self._jobs

    @property
    def checkpoints(self) -> SyncCheckpointManager:
        """Access the underlying SyncCheckpointManager."""
        return self._checkpoints

    async def start_sync(
        self,
        *,
        connector_id: str,
        connector_type: str,
        config: Optional[Dict[str, Any]] = None,
        sync_mode: str = SyncMode.FULL.value,
        tenant_id: Optional[str] = None,
        resume: bool = True,
    ) -> SyncJob:
        """Create a SyncJob and execute it immediately.

        Args:
            connector_id: Connector config UUID.
            connector_type: Registered connector type key.
            config: Connector configuration dict.
            sync_mode: full | incremental | delta.
            tenant_id: Optional tenant key.
            resume: If True, load checkpoint cursor for incremental mode.

        Returns:
            The completed (or failed) SyncJob.
        """
        # Resolve resume cursor
        cursor: Optional[str] = None
        if sync_mode == SyncMode.INCREMENTAL.value and resume:
            cursor = await self._checkpoints.get(connector_id)
            logger.info(
                "Incremental sync for %s: resume cursor=%s",
                connector_id,
                cursor,
            )

        job = await self._jobs.create_job(
            connector_id=connector_id,
            sync_mode=sync_mode,
            tenant_id=tenant_id,
            cursor=cursor,
        )
        await self._session.commit()

        return await self.execute_job(
            job.id,
            connector_type=connector_type,
            config=config or {},
        )

    async def execute_job(
        self,
        job_id: str,
        *,
        connector_type: str,
        config: Dict[str, Any],
    ) -> SyncJob:
        """Execute an existing SyncJob.

        Args:
            job_id: SyncJob UUID.
            connector_type: Registered connector type key.
            config: Connector configuration.

        Returns:
            The updated SyncJob.
        """
        job = await self._jobs.get_job(job_id)
        if job is None:
            raise ConnectorSyncException(
                message=f"SyncJob '{job_id}' not found",
                details={"job_id": job_id},
            )

        await self._jobs.mark_running(job_id)
        await self._session.commit()

        success_count = 0
        failed_count = 0
        events: List[SyncEvent] = []
        current_cursor = job.cursor

        try:
            # Create connector instance
            if not connector_registry.is_registered(connector_type):
                raise ConnectorException(
                    message=f"Unknown connector type '{connector_type}'",
                    details={"connector_type": connector_type},
                )
            connector = connector_registry.create(connector_type, config=config)

            # Call connector.sync() — supports both SyncResult and List returns
            raw_result = await connector.sync(
                sync_mode=job.sync_mode,
                cursor=current_cursor,
            )
            result = normalize_sync_result(raw_result)

            logger.info(
                "SyncJob %s: fetched %d documents (has_more=%s, next_cursor=%s)",
                job_id,
                len(result.documents),
                result.has_more,
                result.next_cursor,
            )

            # Process each document
            for doc in result.documents:
                try:
                    event = await self._process_document(
                        doc,
                        job_id=job_id,
                        connector_id=job.connector_id,
                    )
                    events.append(event)
                    success_count += 1
                except Exception as exc:
                    failed_count += 1
                    logger.warning(
                        "SyncJob %s: failed to process document %s: %s",
                        job_id,
                        doc.id,
                        exc,
                    )

            # Save checkpoint if we have a next_cursor
            if result.next_cursor:
                current_cursor = result.next_cursor
                await self._checkpoints.save(
                    job.connector_id,
                    result.next_cursor,
                    sync_job_id=job_id,
                )
                await self._jobs.update_cursor(job_id, result.next_cursor)

            # Mark job complete
            updated = await self._jobs.mark_success(
                job_id,
                total_count=result.total_count or len(result.documents),
                success_count=success_count,
                failed_count=failed_count,
                cursor=current_cursor,
            )
            await self._session.commit()
            logger.info(
                "SyncJob %s completed: success=%d failed=%d",
                job_id,
                success_count,
                failed_count,
            )
            return updated or job

        except Exception as exc:
            # On failure: preserve cursor for resume
            if current_cursor:
                await self._checkpoints.save(
                    job.connector_id,
                    current_cursor,
                    sync_job_id=job_id,
                )
            updated = await self._jobs.mark_failed(
                job_id,
                error=str(exc),
                cursor=current_cursor,
                total_count=success_count + failed_count,
                success_count=success_count,
                failed_count=failed_count,
            )
            await self._session.commit()
            logger.error("SyncJob %s failed: %s", job_id, exc)
            return updated or job

    async def _process_document(
        self,
        doc: ConnectorDocument,
        *,
        job_id: str,
        connector_id: str,
    ) -> SyncEvent:
        """Process a single document: emit event + enqueue to pipeline.

        Args:
            doc: The connector document.
            job_id: Parent SyncJob UUID.
            connector_id: Connector UUID.

        Returns:
            The emitted SyncEvent.
        """
        # Determine event type (CREATE by default; UPDATE if metadata says so)
        event_type = SyncEventType.CREATE
        if doc.metadata.get("sync_event") == "update":
            event_type = SyncEventType.UPDATE
        elif doc.metadata.get("sync_event") == "delete":
            event_type = SyncEventType.DELETE

        event = SyncEvent(
            event_type=event_type,
            document_id=doc.id,
            connector_id=connector_id,
            sync_job_id=job_id,
            payload={
                "title": doc.title,
                "url": doc.url,
                "updated_at": doc.updated_at,
            },
        )

        # Persist event
        await self._jobs.record_event(
            sync_job_id=job_id,
            connector_id=connector_id,
            event_type=event_type.value,
            document_id=doc.id,
            payload=event.payload,
        )

        # Enqueue to DocumentPipeline via TaskQueue (skip DELETE)
        if event_type != SyncEventType.DELETE:
            await self._enqueue_document(doc, connector_id=connector_id, job_id=job_id)

        return event

    async def _enqueue_document(
        self,
        doc: ConnectorDocument,
        *,
        connector_id: str,
        job_id: str,
    ) -> None:
        """Enqueue a document into the TaskQueue for pipeline processing.

        Args:
            doc: The connector document.
            connector_id: Connector UUID.
            job_id: SyncJob UUID.
        """
        from app.task.queue import TaskQueue

        queue = TaskQueue()
        await queue.enqueue(
            self._session,
            task_type="connector_sync",
            payload={
                "title": doc.title,
                "content": doc.content,
                "metadata": {
                    **(doc.metadata or {}),
                    "connector_id": connector_id,
                    "sync_job_id": job_id,
                    "external_id": doc.id,
                    "external_url": doc.url,
                },
            },
        )
