"""Connector lifecycle management.

Provides a lifecycle manager that tracks connector state transitions
and ensures proper initialization / start / stop / destroy sequences.

States:
    REGISTERED:   Connector class is registered but not yet instantiated.
    INITIALIZING: Connector instance is being set up (HTTP client, auth, etc.).
    READY:        Connector is initialized and ready for sync operations.
    RUNNING:      Connector is currently executing a sync operation.
    FAILED:       Connector encountered an unrecoverable error.
    DISABLED:     Connector has been administratively disabled.
    DESTROYED:    Connector has been destroyed and its resources released.
"""

from __future__ import annotations

import enum
import logging
from typing import Dict

from app.connector.base import BaseConnector
from app.core.exceptions import ConnectorException

logger = logging.getLogger(__name__)


class ConnectorState(str, enum.Enum):
    """Enumeration of possible connector lifecycle states."""

    REGISTERED = "registered"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    DISABLED = "disabled"
    DESTROYED = "destroyed"


# ── Valid state transitions ──
_VALID_TRANSITIONS: Dict[ConnectorState, set[ConnectorState]] = {
    ConnectorState.REGISTERED: {ConnectorState.INITIALIZING, ConnectorState.DISABLED},
    ConnectorState.INITIALIZING: {ConnectorState.READY, ConnectorState.FAILED},
    ConnectorState.READY: {
        ConnectorState.RUNNING,
        ConnectorState.DISABLED,
        ConnectorState.DESTROYED,
    },
    ConnectorState.RUNNING: {ConnectorState.READY, ConnectorState.FAILED},
    ConnectorState.FAILED: {ConnectorState.INITIALIZING, ConnectorState.DISABLED},
    ConnectorState.DISABLED: {ConnectorState.REGISTERED, ConnectorState.DESTROYED},
    ConnectorState.DESTROYED: {ConnectorState.INITIALIZING},
}


class ConnectorLifecycleManager:
    """Manages the lifecycle of a connector instance.

    Each connector has a state machine that must follow valid transitions.
    All state changes are logged for auditability.
    """

    def __init__(self) -> None:
        self._states: Dict[str, ConnectorState] = {}
        self._instances: Dict[str, BaseConnector] = {}

    def get_state(self, connector_id: str) -> ConnectorState:
        """Get the current lifecycle state of a connector.

        Args:
            connector_id: The connector config ID.

        Returns:
            Current ConnectorState.
        """
        return self._states.get(connector_id, ConnectorState.REGISTERED)

    def get_instances(self) -> Dict[str, BaseConnector]:
        """Get all active connector instances.

        Returns:
            Dict mapping connector_id to BaseConnector instance.
        """
        return dict(self._instances)

    def is_ready(self, connector_id: str) -> bool:
        """Check if a connector is in a ready state for sync.

        Args:
            connector_id: The connector config ID.

        Returns:
            True if state is READY.
        """
        return self._states.get(connector_id) == ConnectorState.READY

    def _transition(
        self,
        connector_id: str,
        target: ConnectorState,
    ) -> None:
        """Attempt a state transition with validation.

        Args:
            connector_id: The connector config ID.
            target: Desired new state.

        Raises:
            ConnectorException: If the transition is invalid.
        """
        current = self.get_state(connector_id)
        allowed = _VALID_TRANSITIONS.get(current, set())

        if target not in allowed:
            raise ConnectorException(
                message=(
                    f"Invalid state transition: {current.value} -> {target.value} "
                    f"for connector {connector_id}"
                ),
                details={
                    "connector_id": connector_id,
                    "current_state": current.value,
                    "target_state": target.value,
                },
            )

        logger.info(
            "Connector %s state: %s -> %s",
            connector_id,
            current.value,
            target.value,
        )
        self._states[connector_id] = target

    async def initialize(
        self,
        connector_id: str,
        connector: BaseConnector,
    ) -> None:
        """Initialize a connector instance.

        Transitions: REGISTERED -> INITIALIZING -> READY (or FAILED).

        Args:
            connector_id: The connector config ID.
            connector: The connector instance to initialize.

        Raises:
            ConnectorException: On initialization failure.
        """
        self._transition(connector_id, ConnectorState.INITIALIZING)
        self._instances[connector_id] = connector

        try:
            # Validate config first
            valid = await connector.validate_config()
            if not valid:
                raise ConnectorException(
                    message="Connector configuration validation failed",
                    details={"connector_id": connector_id},
                )

            # Initialize connector resources
            await connector.initialize()
            self._transition(connector_id, ConnectorState.READY)
        except Exception as exc:
            self._transition(connector_id, ConnectorState.FAILED)
            raise ConnectorException(
                message=f"Connector initialization failed: {exc}",
                details={"connector_id": connector_id, "error": str(exc)},
            ) from exc

    async def start(self, connector_id: str) -> None:
        """Transition a connector to running state.

        Args:
            connector_id: The connector config ID.

        Raises:
            ConnectorException: If not READY.
        """
        if not self.is_ready(connector_id):
            raise ConnectorException(
                message="Cannot start connector that is not READY",
                details={
                    "connector_id": connector_id,
                    "current_state": self.get_state(connector_id).value,
                },
            )
        self._transition(connector_id, ConnectorState.RUNNING)

    async def stop(self, connector_id: str) -> None:
        """Transition a connector back to ready state.

        Args:
            connector_id: The connector config ID.
        """
        if self.get_state(connector_id) != ConnectorState.RUNNING:
            return
        self._transition(connector_id, ConnectorState.READY)

    async def fail(self, connector_id: str) -> None:
        """Mark a connector as failed.

        Args:
            connector_id: The connector config ID.
        """
        current = self.get_state(connector_id)
        if current == ConnectorState.RUNNING:
            self._transition(connector_id, ConnectorState.FAILED)

    async def destroy(self, connector_id: str) -> None:
        """Destroy a connector, releasing all resources.

        Transitions: any state -> DESTROYED.

        Args:
            connector_id: The connector config ID.
        """
        connector = self._instances.pop(connector_id, None)
        if connector is not None:
            try:
                await connector.cleanup()
            except Exception as exc:
                logger.warning(
                    "Cleanup failed for connector %s: %s",
                    connector_id,
                    exc,
                )
        self._states[connector_id] = ConnectorState.DESTROYED
        logger.info("Connector %s destroyed", connector_id)

    async def restart(self, connector_id: str) -> None:
        """Restart a connector: destroy then re-initialize.

        Args:
            connector_id: The connector config ID.
        """
        instance = self._instances.get(connector_id)
        if instance is None:
            raise ConnectorException(
                message="Cannot restart connector that has no instance",
                details={"connector_id": connector_id},
            )
        await self.destroy(connector_id)
        await self.initialize(connector_id, instance)


# Module-level singleton
lifecycle_manager = ConnectorLifecycleManager()
