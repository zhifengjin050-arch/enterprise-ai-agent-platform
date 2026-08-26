"""Tests for ConnectorLifecycleManager and ConnectorState."""

from __future__ import annotations

from typing import List, Optional

import pytest

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.lifecycle import (
    _VALID_TRANSITIONS,
    ConnectorLifecycleManager,
    ConnectorState,
)
from app.core.exceptions import ConnectorException

# ── Dummy connector for testing ──


class DummyLifecycleConnector(BaseConnector):
    """Dummy connector for lifecycle testing."""

    name: str = "DummyLifecycle"
    connector_type: str = "dummy_lifecycle"

    async def test_connection(self) -> bool:
        return True

    async def fetch_documents(self) -> List[ConnectorDocument]:
        return []

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        return None

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> List[ConnectorDocument]:
        return []


class FailingInitConnector(BaseConnector):
    """Connector whose validate_config raises."""

    name: str = "FailingInit"
    connector_type: str = "failing_init"

    async def test_connection(self) -> bool:
        return True

    async def fetch_documents(self) -> List[ConnectorDocument]:
        return []

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        return None

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> List[ConnectorDocument]:
        return []

    async def validate_config(self) -> bool:
        return False


# ── Tests ──


class TestConnectorState:
    """Tests for the ConnectorState enum."""

    def test_enum_values(self) -> None:
        """Test expected state values."""
        assert ConnectorState.REGISTERED.value == "registered"
        assert ConnectorState.INITIALIZING.value == "initializing"
        assert ConnectorState.READY.value == "ready"
        assert ConnectorState.RUNNING.value == "running"
        assert ConnectorState.FAILED.value == "failed"
        assert ConnectorState.DISABLED.value == "disabled"
        assert ConnectorState.DESTROYED.value == "destroyed"


class TestValidTransitions:
    """Test the valid transition table."""

    def test_registered_transitions(self) -> None:
        """Test transitions from REGISTERED."""
        allowed = _VALID_TRANSITIONS[ConnectorState.REGISTERED]
        assert ConnectorState.INITIALIZING in allowed
        assert ConnectorState.DISABLED in allowed
        assert ConnectorState.READY not in allowed
        assert ConnectorState.DESTROYED not in allowed

    def test_destroyed_outgoing(self) -> None:
        """Test DESTROYED allows re-initialization for restart."""
        allowed = _VALID_TRANSITIONS[ConnectorState.DESTROYED]
        assert ConnectorState.INITIALIZING in allowed


class TestConnectorLifecycleManager:
    """Tests for the lifecycle manager."""

    def setup_method(self) -> None:
        self.manager = ConnectorLifecycleManager()

    def test_initial_state(self) -> None:
        """Test unregistered connector returns REGISTERED."""
        state = self.manager.get_state("nonexistent")
        assert state == ConnectorState.REGISTERED

    @pytest.mark.asyncio
    async def test_initialize_success(self) -> None:
        """Test successful initialization flow."""
        conn = DummyLifecycleConnector(config={"key": "val"})
        cid = "test-conn-1"

        # Should transition REGISTERED -> INITIALIZING -> READY
        await self.manager.initialize(cid, conn)

        assert self.manager.is_ready(cid)
        assert self.manager.get_state(cid) == ConnectorState.READY

    @pytest.mark.asyncio
    async def test_initialize_failure(self) -> None:
        """Test initialization failure transitions to FAILED."""
        conn = FailingInitConnector(config={})
        cid = "test-conn-2"

        with pytest.raises(ConnectorException):
            await self.manager.initialize(cid, conn)

        state = self.manager.get_state(cid)
        assert state == ConnectorState.FAILED

    @pytest.mark.asyncio
    async def test_start_ready_connector(self) -> None:
        """Test start from READY state."""
        conn = DummyLifecycleConnector()
        cid = "test-conn-3"
        await self.manager.initialize(cid, conn)
        await self.manager.start(cid)

        assert self.manager.get_state(cid) == ConnectorState.RUNNING

    @pytest.mark.asyncio
    async def test_start_non_ready_raises(self) -> None:
        """Test start from non-READY state raises."""
        cid = "test-conn-4"
        with pytest.raises(ConnectorException, match="not READY"):
            await self.manager.start(cid)

    @pytest.mark.asyncio
    async def test_stop_running_connector(self) -> None:
        """Test stop returns to READY."""
        conn = DummyLifecycleConnector()
        cid = "test-conn-5"
        await self.manager.initialize(cid, conn)
        await self.manager.start(cid)
        await self.manager.stop(cid)

        assert self.manager.get_state(cid) == ConnectorState.READY

    @pytest.mark.asyncio
    async def test_fail_running(self) -> None:
        """Test fail transitions RUNNING -> FAILED."""
        conn = DummyLifecycleConnector()
        cid = "test-conn-6"
        await self.manager.initialize(cid, conn)
        await self.manager.start(cid)
        await self.manager.fail(cid)

        assert self.manager.get_state(cid) == ConnectorState.FAILED

    @pytest.mark.asyncio
    async def test_destroy_releases_instance(self) -> None:
        """Test destroy calls cleanup and sets DESTROYED."""
        conn = DummyLifecycleConnector()
        cid = "test-conn-7"
        await self.manager.initialize(cid, conn)
        await self.manager.destroy(cid)

        assert self.manager.get_state(cid) == ConnectorState.DESTROYED
        instances = self.manager.get_instances()
        assert cid not in instances

    @pytest.mark.asyncio
    async def test_restart(self) -> None:
        """Test restart: destroy then re-initialize."""
        conn = DummyLifecycleConnector()
        cid = "test-conn-8"
        await self.manager.initialize(cid, conn)
        await self.manager.restart(cid)

        assert self.manager.is_ready(cid)

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self) -> None:
        """Test invalid transition raises."""
        conn = DummyLifecycleConnector()
        cid = "test-conn-9"
        await self.manager.initialize(cid, conn)

        # Can't go from READY to INITIALIZING
        with pytest.raises(ConnectorException, match="Invalid state transition"):
            # Directly call _transition to simulate invalid move
            self.manager._transition(cid, ConnectorState.INITIALIZING)
