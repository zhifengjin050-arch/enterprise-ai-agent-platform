"""Tests for SyncCheckpointManager."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.sync_engine.checkpoint import SyncCheckpointManager


class TestSyncCheckpointManager:
    """Tests for checkpoint save / get / clear."""

    async def test_save_and_get(self, db_session: AsyncSession) -> None:
        """Test creating and retrieving a checkpoint."""
        mgr = SyncCheckpointManager(db_session)
        assert await mgr.get("conn-1") is None

        cp = await mgr.save("conn-1", "cursor-v1", sync_job_id="job-1")
        assert cp.cursor == "cursor-v1"
        assert cp.connector_id == "conn-1"
        assert cp.sync_job_id == "job-1"

        cursor = await mgr.get("conn-1")
        assert cursor == "cursor-v1"

    async def test_upsert(self, db_session: AsyncSession) -> None:
        """Test updating an existing checkpoint."""
        mgr = SyncCheckpointManager(db_session)
        await mgr.save("conn-2", "cursor-v1")
        cp = await mgr.save("conn-2", "cursor-v2", sync_job_id="job-2")
        assert cp.cursor == "cursor-v2"
        assert cp.sync_job_id == "job-2"

        # Only one checkpoint per connector
        cursor = await mgr.get("conn-2")
        assert cursor == "cursor-v2"

    async def test_get_checkpoint(self, db_session: AsyncSession) -> None:
        """Test get_checkpoint returns full record."""
        mgr = SyncCheckpointManager(db_session)
        await mgr.save("conn-3", "cursor-abc")
        record = await mgr.get_checkpoint("conn-3")
        assert record is not None
        assert record.cursor == "cursor-abc"
        assert record.updated_at is not None

    async def test_clear(self, db_session: AsyncSession) -> None:
        """Test clearing a checkpoint."""
        mgr = SyncCheckpointManager(db_session)
        await mgr.save("conn-4", "cursor-x")
        assert await mgr.clear("conn-4") is True
        assert await mgr.get("conn-4") is None
        assert await mgr.clear("conn-4") is False  # already cleared

    async def test_to_dict(self, db_session: AsyncSession) -> None:
        """Test SyncCheckpoint.to_dict."""
        mgr = SyncCheckpointManager(db_session)
        cp = await mgr.save("conn-5", "cursor-dict")
        d = cp.to_dict()
        assert d["connector_id"] == "conn-5"
        assert d["cursor"] == "cursor-dict"
        assert "updated_at" in d
        assert "id" in d