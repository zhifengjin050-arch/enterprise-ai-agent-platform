"""SyncJob manager — CRUD and lifecycle operations for SyncJob records.

Separates persistence concerns from the SyncEngine orchestration logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.sync_engine.models import SyncEventRecord, SyncJob, SyncJobStatus

logger = logging.getLogger(__name__)


class SyncJobManager:
    """Repository + lifecycle helpers for SyncJob and SyncEventRecord."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── SyncJob CRUD ──

    async def create_job(
        self,
        *,
        connector_id: str,
        sync_mode: str = "full",
        tenant_id: Optional[str] = None,
        cursor: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> SyncJob:
        """Create a new SyncJob in PENDING status.

        Args:
            connector_id: Target connector config UUID.
            sync_mode: full | incremental | delta.
            tenant_id: Optional tenant isolation key.
            cursor: Optional resume cursor.
            metadata_json: Optional extra metadata.

        Returns:
            The created SyncJob.
        """
        job = SyncJob(
            connector_id=connector_id,
            sync_mode=sync_mode,
            tenant_id=tenant_id,
            cursor=cursor,
            status=SyncJobStatus.PENDING.value,
            metadata_json=metadata_json,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        logger.info(
            "SyncJob created: id=%s connector=%s mode=%s",
            job.id,
            connector_id,
            sync_mode,
        )
        return job

    async def get_job(self, job_id: str) -> Optional[SyncJob]:
        """Get a SyncJob by ID.

        Args:
            job_id: UUID string.

        Returns:
            SyncJob or None.
        """
        stmt = select(SyncJob).where(SyncJob.id == job_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        *,
        connector_id: Optional[str] = None,
        status: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SyncJob]:
        """List SyncJobs with optional filters.

        Args:
            connector_id: Filter by connector.
            status: Filter by status.
            tenant_id: Filter by tenant.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of SyncJob sorted by created_at desc.
        """
        stmt = select(SyncJob).order_by(SyncJob.created_at.desc())
        if connector_id is not None:
            stmt = stmt.where(SyncJob.connector_id == connector_id)
        if status is not None:
            stmt = stmt.where(SyncJob.status == status)
        if tenant_id is not None:
            stmt = stmt.where(SyncJob.tenant_id == tenant_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_running(self, job_id: str) -> Optional[SyncJob]:
        """Transition a job to RUNNING and set started_at.

        Args:
            job_id: UUID string.

        Returns:
            Updated SyncJob or None.
        """
        job = await self.get_job(job_id)
        if job is None:
            return None
        job.status = SyncJobStatus.RUNNING.value
        job.started_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def mark_success(
        self,
        job_id: str,
        *,
        total_count: int = 0,
        success_count: int = 0,
        failed_count: int = 0,
        cursor: Optional[str] = None,
    ) -> Optional[SyncJob]:
        """Mark a job as SUCCESS (or PARTIAL if some failures).

        Args:
            job_id: UUID string.
            total_count: Total documents.
            success_count: Successfully processed.
            failed_count: Failed documents.
            cursor: Final cursor value.

        Returns:
            Updated SyncJob or None.
        """
        job = await self.get_job(job_id)
        if job is None:
            return None
        if failed_count > 0 and success_count > 0:
            job.status = SyncJobStatus.PARTIAL.value
        elif failed_count > 0 and success_count == 0:
            job.status = SyncJobStatus.FAILED.value
        else:
            job.status = SyncJobStatus.SUCCESS.value
        job.total_count = total_count
        job.success_count = success_count
        job.failed_count = failed_count
        if cursor is not None:
            job.cursor = cursor
        job.finished_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def mark_failed(
        self,
        job_id: str,
        *,
        error: str,
        cursor: Optional[str] = None,
        total_count: int = 0,
        success_count: int = 0,
        failed_count: int = 0,
    ) -> Optional[SyncJob]:
        """Mark a job as FAILED, preserving the cursor for resume.

        Args:
            job_id: UUID string.
            error: Error message.
            cursor: Last known good cursor (for resume).
            total_count: Documents discovered so far.
            success_count: Successfully processed so far.
            failed_count: Failed so far.

        Returns:
            Updated SyncJob or None.
        """
        job = await self.get_job(job_id)
        if job is None:
            return None
        job.status = SyncJobStatus.FAILED.value
        job.error = error
        job.total_count = total_count
        job.success_count = success_count
        job.failed_count = failed_count
        if cursor is not None:
            job.cursor = cursor
        job.finished_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(job)
        logger.warning("SyncJob %s failed: %s", job_id, error)
        return job

    async def update_cursor(self, job_id: str, cursor: str) -> None:
        """Update the job's cursor mid-flight (for checkpointing).

        Args:
            job_id: UUID string.
            cursor: New cursor value.
        """
        job = await self.get_job(job_id)
        if job is not None:
            job.cursor = cursor
            await self._session.flush()

    # ── SyncEvent persistence ──

    async def record_event(
        self,
        *,
        sync_job_id: str,
        connector_id: str,
        event_type: str,
        document_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> SyncEventRecord:
        """Persist a sync event.

        Args:
            sync_job_id: Parent SyncJob UUID.
            connector_id: Connector UUID.
            event_type: create | update | delete.
            document_id: External document ID.
            payload: Optional event payload.

        Returns:
            The created SyncEventRecord.
        """
        record = SyncEventRecord(
            sync_job_id=sync_job_id,
            connector_id=connector_id,
            event_type=event_type,
            document_id=document_id,
            payload=payload,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def list_events(
        self,
        sync_job_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SyncEventRecord]:
        """List events for a SyncJob.

        Args:
            sync_job_id: Parent SyncJob UUID.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of SyncEventRecord sorted by created_at asc.
        """
        stmt = (
            select(SyncEventRecord)
            .where(SyncEventRecord.sync_job_id == sync_job_id)
            .order_by(SyncEventRecord.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
