"""Tests for SyncJob model and SyncJobManager."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.sync_engine.job_manager import SyncJobManager
from app.sync_engine.models import SyncJobStatus


class TestSyncJobManager:
    """Tests for SyncJob CRUD and lifecycle."""

    async def test_create_job(self, db_session: AsyncSession) -> None:
        """Test creating a SyncJob in PENDING status."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(
            connector_id="conn-1",
            sync_mode="full",
            tenant_id="tenant-1",
        )
        assert job.id is not None
        assert job.status == SyncJobStatus.PENDING.value
        assert job.connector_id == "conn-1"
        assert job.sync_mode == "full"
        assert job.total_count == 0

    async def test_get_job(self, db_session: AsyncSession) -> None:
        """Test retrieving a SyncJob by ID."""
        mgr = SyncJobManager(db_session)
        created = await mgr.create_job(connector_id="conn-2", sync_mode="incremental")
        fetched = await mgr.get_job(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.sync_mode == "incremental"

    async def test_get_job_not_found(self, db_session: AsyncSession) -> None:
        """Test get returns None for missing ID."""
        mgr = SyncJobManager(db_session)
        assert await mgr.get_job("nonexistent") is None

    async def test_mark_running(self, db_session: AsyncSession) -> None:
        """Test transitioning to RUNNING sets started_at."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(connector_id="conn-3")
        updated = await mgr.mark_running(job.id)
        assert updated is not None
        assert updated.status == SyncJobStatus.RUNNING.value
        assert updated.started_at is not None

    async def test_mark_success(self, db_session: AsyncSession) -> None:
        """Test marking a job as SUCCESS."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(connector_id="conn-4")
        await mgr.mark_running(job.id)
        updated = await mgr.mark_success(
            job.id,
            total_count=10,
            success_count=10,
            failed_count=0,
            cursor="cursor-xyz",
        )
        assert updated is not None
        assert updated.status == SyncJobStatus.SUCCESS.value
        assert updated.total_count == 10
        assert updated.success_count == 10
        assert updated.cursor == "cursor-xyz"
        assert updated.finished_at is not None

    async def test_mark_partial(self, db_session: AsyncSession) -> None:
        """Test partial success when some documents fail."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(connector_id="conn-5")
        await mgr.mark_running(job.id)
        updated = await mgr.mark_success(
            job.id,
            total_count=10,
            success_count=7,
            failed_count=3,
        )
        assert updated is not None
        assert updated.status == SyncJobStatus.PARTIAL.value

    async def test_mark_failed(self, db_session: AsyncSession) -> None:
        """Test marking a job as FAILED preserves cursor."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(connector_id="conn-6", cursor="old-cursor")
        await mgr.mark_running(job.id)
        updated = await mgr.mark_failed(
            job.id,
            error="Connection timeout",
            cursor="resume-cursor",
            success_count=2,
            failed_count=1,
        )
        assert updated is not None
        assert updated.status == SyncJobStatus.FAILED.value
        assert updated.error == "Connection timeout"
        assert updated.cursor == "resume-cursor"
        assert updated.finished_at is not None

    async def test_list_jobs(self, db_session: AsyncSession) -> None:
        """Test listing jobs with filters."""
        mgr = SyncJobManager(db_session)
        await mgr.create_job(connector_id="conn-a", sync_mode="full")
        await mgr.create_job(connector_id="conn-a", sync_mode="incremental")
        await mgr.create_job(connector_id="conn-b", sync_mode="full")

        jobs = await mgr.list_jobs(connector_id="conn-a")
        assert len(jobs) == 2

        jobs_all = await mgr.list_jobs()
        assert len(jobs_all) >= 3

    async def test_record_and_list_events(self, db_session: AsyncSession) -> None:
        """Test persisting and listing sync events."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(connector_id="conn-evt")

        await mgr.record_event(
            sync_job_id=job.id,
            connector_id="conn-evt",
            event_type="create",
            document_id="doc-1",
            payload={"title": "Doc One"},
        )
        await mgr.record_event(
            sync_job_id=job.id,
            connector_id="conn-evt",
            event_type="update",
            document_id="doc-2",
        )

        events = await mgr.list_events(job.id)
        assert len(events) == 2
        assert events[0].event_type == "create"
        assert events[1].event_type == "update"

    async def test_to_dict(self, db_session: AsyncSession) -> None:
        """Test SyncJob.to_dict serialization."""
        mgr = SyncJobManager(db_session)
        job = await mgr.create_job(connector_id="conn-dict", sync_mode="delta")
        d = job.to_dict()
        assert d["id"] == job.id
        assert d["connector_id"] == "conn-dict"
        assert d["sync_mode"] == "delta"
        assert d["status"] == "pending"
        assert "created_at" in d