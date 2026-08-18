"""Tests for sync failure handling and retry behavior."""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.base import ConnectorDocument
from app.connector.registry import ConnectorRegistry
from app.connector.retry import ConnectorRetryPolicy, is_retryable
from app.core.exceptions import (
    ConnectorAuthException,
    ConnectorConfigError,
    ConnectorConnectionException,
)
from app.sync_engine.events import SyncEvent, SyncEventType
from app.sync_engine.models import SyncJobStatus
from app.sync_engine.sync_engine import SyncEngine
from tests.sync_engine.conftest import FakeConnector


class TestFailureRetry:
    """Tests for failure classification and SyncEngine failure handling."""

    def test_connection_error_is_retryable(self) -> None:
        """Test ConnectorConnectionException is retryable."""
        assert is_retryable(ConnectorConnectionException()) is True

    def test_auth_error_not_retryable(self) -> None:
        """Test ConnectorAuthException is NOT retryable."""
        assert is_retryable(ConnectorAuthException()) is False

    def test_config_error_not_retryable(self) -> None:
        """Test ConnectorConfigError is NOT retryable."""
        assert is_retryable(ConnectorConfigError()) is False

    async def test_retry_policy_retries_connection_error(self) -> None:
        """Test ConnectorRetryPolicy retries then succeeds."""
        calls = {"n": 0}

        async def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectorConnectionException(message="timeout")
            return "ok"

        policy = ConnectorRetryPolicy(max_retries=3, backoff_base=0.01, backoff_max=0.05)
        result = await policy.execute(flaky, context="test")
        assert result == "ok"
        assert calls["n"] == 3

    async def test_retry_policy_no_retry_on_auth(self) -> None:
        """Test auth errors are not retried."""
        calls = {"n": 0}

        async def auth_fail() -> str:
            calls["n"] += 1
            raise ConnectorAuthException(message="bad token")

        policy = ConnectorRetryPolicy(max_retries=3, backoff_base=0.01)
        with pytest.raises(ConnectorAuthException):
            await policy.execute(auth_fail, context="auth_test")
        assert calls["n"] == 1

    async def test_engine_marks_failed_on_connector_error(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test SyncEngine marks job FAILED when connector.sync() raises."""
        engine = SyncEngine(db_session)
        registry = ConnectorRegistry()

        class FailConn(FakeConnector):
            connector_type: str = "fail_retry"

        registry.register("fail_retry", FailConn)

        def _create(ctype, *, config=None):
            return FakeConnector(config=config, fail=True)

        registry.create = _create  # type: ignore[method-assign]

        with patch("app.sync_engine.sync_engine.connector_registry", registry):
            job = await engine.start_sync(
                connector_id="conn-fr",
                connector_type="fail_retry",
                sync_mode="full",
            )

        assert job.status == SyncJobStatus.FAILED.value
        assert "Simulated" in (job.error or "")

    async def test_partial_document_failures(
        self,
        db_session: AsyncSession,
        sample_documents: List[ConnectorDocument],
    ) -> None:
        """Test that individual document enqueue failures produce PARTIAL status."""
        engine = SyncEngine(db_session)
        registry = ConnectorRegistry()

        class PartialConn(FakeConnector):
            connector_type: str = "partial"

        registry.register("partial", PartialConn)

        def _create(ctype, *, config=None):
            return FakeConnector(config=config, documents=sample_documents)

        registry.create = _create  # type: ignore[method-assign]

        call_count = {"n": 0}

        async def flaky_enqueue(self, doc, *, connector_id, job_id):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("enqueue failed")

        with patch("app.sync_engine.sync_engine.connector_registry", registry):
            with patch.object(SyncEngine, "_enqueue_document", flaky_enqueue):
                job = await engine.start_sync(
                    connector_id="conn-partial",
                    connector_type="partial",
                    sync_mode="full",
                )

        assert job.status == SyncJobStatus.PARTIAL.value
        assert job.success_count == 2
        assert job.failed_count == 1


class TestSyncEvents:
    """Tests for SyncEvent model."""

    def test_create_event(self) -> None:
        """Test SyncEvent.create factory."""
        event = SyncEvent.create("doc-1", connector_id="c1", sync_job_id="j1")
        assert event.event_type == SyncEventType.CREATE
        assert event.document_id == "doc-1"

    def test_update_event(self) -> None:
        """Test SyncEvent.update factory."""
        event = SyncEvent.update("doc-2")
        assert event.event_type == SyncEventType.UPDATE

    def test_delete_event(self) -> None:
        """Test SyncEvent.delete factory."""
        event = SyncEvent.delete("doc-3")
        assert event.event_type == SyncEventType.DELETE

    def test_to_dict(self) -> None:
        """Test SyncEvent.to_dict."""
        event = SyncEvent.create("doc-1", payload={"title": "T"})
        d = event.to_dict()
        assert d["event_type"] == "create"
        assert d["document_id"] == "doc-1"
        assert d["payload"]["title"] == "T"