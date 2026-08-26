"""Tests for cursor recovery after sync failure."""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.base import ConnectorDocument
from app.connector.registry import ConnectorRegistry
from app.sync_engine.models import SyncJobStatus
from app.sync_engine.sync_engine import SyncEngine
from tests.sync_engine.conftest import FakeConnector


class TestCursorRecovery:
    """Tests for checkpoint-based resume after failure."""

    async def test_failure_preserves_cursor(
        self,
        db_session: AsyncSession,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test that a failed sync preserves the last known cursor."""
        engine = SyncEngine(db_session)

        # Pre-seed a checkpoint
        await engine.checkpoints.save("conn-fail", "2026-01-15T00:00:00Z")
        await db_session.commit()

        registry = ConnectorRegistry()

        class FailConnector(FakeConnector):
            connector_type: str = "fake_fail"

        registry.register("fake_fail", FailConnector)

        def _create(ctype, *, config=None):
            return FakeConnector(config=config, documents=sample_documents, fail=True)

        registry.create = _create  # type: ignore[method-assign]

        with patch("app.sync_engine.sync_engine.connector_registry", registry):
            job = await engine.start_sync(
                connector_id="conn-fail",
                connector_type="fake_fail",
                sync_mode="incremental",
                resume=True,
            )

        assert job.status == SyncJobStatus.FAILED.value
        assert job.error is not None

        # Cursor must still be the pre-failure checkpoint
        cursor = await engine.checkpoints.get("conn-fail")
        assert cursor == "2026-01-15T00:00:00Z"

    async def test_resume_from_saved_cursor(
        self,
        db_session: AsyncSession,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test that a subsequent sync resumes from the saved cursor."""
        engine = SyncEngine(db_session)
        await engine.checkpoints.save("conn-resume", "2026-02-01T00:00:00Z")
        await db_session.commit()

        registry = ConnectorRegistry()

        class ResumeConnector(FakeConnector):
            connector_type: str = "fake_resume"

        registry.register("fake_resume", ResumeConnector)

        def _create(ctype, *, config=None):
            return FakeConnector(config=config, documents=sample_documents)

        registry.create = _create  # type: ignore[method-assign]

        with patch("app.sync_engine.sync_engine.connector_registry", registry):
            with patch.object(SyncEngine, "_enqueue_document", new_callable=AsyncMock):
                job = await engine.start_sync(
                    connector_id="conn-resume",
                    connector_type="fake_resume",
                    sync_mode="incremental",
                    resume=True,
                )

        assert job.status == SyncJobStatus.SUCCESS.value
        # Only doc-3 is newer than 2026-02-01
        assert job.success_count == 1
        cursor = await engine.checkpoints.get("conn-resume")
        assert cursor == "2026-03-01T00:00:00Z"

    async def test_job_cursor_updated_on_success(
        self,
        db_session: AsyncSession,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test that SyncJob.cursor is updated to next_cursor on success."""
        engine = SyncEngine(db_session)
        registry = ConnectorRegistry()

        class OkConnector(FakeConnector):
            connector_type: str = "fake_ok"

        registry.register("fake_ok", OkConnector)

        def _create(ctype, *, config=None):
            return FakeConnector(config=config, documents=sample_documents)

        registry.create = _create  # type: ignore[method-assign]

        with patch("app.sync_engine.sync_engine.connector_registry", registry):
            with patch.object(SyncEngine, "_enqueue_document", new_callable=AsyncMock):
                job = await engine.start_sync(
                    connector_id="conn-ok",
                    connector_type="fake_ok",
                    sync_mode="full",
                )

        assert job.status == SyncJobStatus.SUCCESS.value
        assert job.cursor == "2026-03-01T00:00:00Z"
        assert job.total_count == 3
        assert job.success_count == 3
