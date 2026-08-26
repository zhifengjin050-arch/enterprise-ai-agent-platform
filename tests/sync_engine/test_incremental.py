"""Tests for incremental sync and cursor-based filtering."""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.base import ConnectorDocument
from app.connector.registry import ConnectorRegistry
from app.connector.sync_modes import SyncMode, SyncResult, normalize_sync_result
from app.sync_engine.models import SyncJobStatus
from app.sync_engine.sync_engine import SyncEngine
from tests.sync_engine.conftest import FakeConnector


class TestSyncResult:
    """Tests for SyncResult and normalize_sync_result."""

    def test_from_documents(self) -> None:
        """Test SyncResult.from_documents convenience constructor."""
        docs = [
            ConnectorDocument(id="1", title="A"),
            ConnectorDocument(id="2", title="B"),
        ]
        result = SyncResult.from_documents(docs, next_cursor="c1", has_more=True)
        assert result.total_count == 2
        assert result.next_cursor == "c1"
        assert result.has_more is True
        assert result.cursor is not None
        assert result.cursor.value == "c1"

    def test_normalize_from_list(self) -> None:
        """Test normalize_sync_result wraps a plain list."""
        docs = [ConnectorDocument(id="1")]
        result = normalize_sync_result(docs)
        assert isinstance(result, SyncResult)
        assert len(result.documents) == 1

    def test_normalize_from_sync_result(self) -> None:
        """Test normalize_sync_result passes through SyncResult."""
        original = SyncResult.from_documents([], next_cursor="x")
        result = normalize_sync_result(original)
        assert result is original

    def test_to_dict(self) -> None:
        """Test SyncResult.to_dict includes Phase 4 fields."""
        result = SyncResult.from_documents(
            [ConnectorDocument(id="1", title="T")],
            next_cursor="nc",
            has_more=False,
        )
        d = result.to_dict()
        assert "next_cursor" in d
        assert "has_more" in d
        assert d["next_cursor"] == "nc"
        assert d["total_count"] == 1


class TestIncrementalSync:
    """Tests for incremental sync with cursor filtering."""

    async def test_full_sync_returns_all(
        self,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test FULL sync returns all documents."""
        conn = FakeConnector(documents=sample_documents)
        result = await conn.sync(sync_mode=SyncMode.FULL.value)
        assert len(result.documents) == 3
        assert result.next_cursor == "2026-03-01T00:00:00Z"

    async def test_incremental_filters_by_cursor(
        self,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test INCREMENTAL sync skips documents <= cursor."""
        conn = FakeConnector(documents=sample_documents)
        result = await conn.sync(
            sync_mode=SyncMode.INCREMENTAL.value,
            cursor="2026-01-01T00:00:00Z",
        )
        # doc-1 has updated_at == cursor → skipped; doc-2 and doc-3 remain
        assert len(result.documents) == 2
        ids = {d.id for d in result.documents}
        assert "doc-1" not in ids
        assert "doc-2" in ids
        assert "doc-3" in ids

    async def test_incremental_empty_when_caught_up(
        self,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test INCREMENTAL returns empty when cursor is at max."""
        conn = FakeConnector(documents=sample_documents)
        result = await conn.sync(
            sync_mode=SyncMode.INCREMENTAL.value,
            cursor="2026-03-01T00:00:00Z",
        )
        assert len(result.documents) == 0
        assert result.next_cursor == "2026-03-01T00:00:00Z"

    async def test_engine_incremental_with_checkpoint(
        self,
        db_session: AsyncSession,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test SyncEngine loads checkpoint and runs incremental sync."""
        registry = ConnectorRegistry()

        class BoundFake(FakeConnector):
            pass

        BoundFake.connector_type = "fake_inc"
        registry.register("fake_inc", BoundFake)

        # Pre-seed checkpoint
        engine = SyncEngine(db_session)
        await engine.checkpoints.save("conn-inc", "2026-01-01T00:00:00Z")
        await db_session.commit()

        # Patch the module-level registry used by SyncEngine
        with patch("app.sync_engine.sync_engine.connector_registry", registry):
            # Also need FakeConnector to use sample_documents — override create
            original_create = registry.create

            def _create(ctype, *, config=None):
                return FakeConnector(config=config, documents=sample_documents)

            registry.create = _create  # type: ignore[method-assign]

            with patch.object(SyncEngine, "_enqueue_document", new_callable=AsyncMock):
                job = await engine.start_sync(
                    connector_id="conn-inc",
                    connector_type="fake_inc",
                    sync_mode=SyncMode.INCREMENTAL.value,
                    resume=True,
                )

        assert job.status in (
            SyncJobStatus.SUCCESS.value,
            SyncJobStatus.PARTIAL.value,
        )
        assert job.success_count == 2  # doc-2, doc-3
        # Checkpoint should advance to latest
        cursor = await engine.checkpoints.get("conn-inc")
        assert cursor == "2026-03-01T00:00:00Z"
