"""Connector factory — creates connector instances by type.

Centralises instantiation logic so that business code never needs
to import concrete connector classes.  The factory delegates to the
ConnectorRegistry to resolve the class and handles lifecycle setup.

Usage:
    factory = ConnectorFactory()
    feishu = await factory.create("feishu", config={...})
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.connector.base import BaseConnector
from app.connector.lifecycle import lifecycle_manager
from app.connector.registry import connector_registry
from app.core.exceptions import ConnectorConfigError

logger = logging.getLogger(__name__)


class ConnectorFactory:
    """Factory for creating and initialising connector instances.

    Encapsulates the instantiation + lifecycle initialisation workflow so
    callers only need to specify the type and configuration.
    """

    async def create(
        self,
        connector_type: str,
        *,
        config: Optional[Dict[str, Any]] = None,
        connector_id: Optional[str] = None,
    ) -> BaseConnector:
        """Create and fully initialise a connector instance.

        Args:
            connector_type: Registered type key (e.g. "feishu").
            config: Connector-specific configuration.
            connector_id: Optional ID to track lifecycle state.

        Returns:
            An initialised BaseConnector instance in READY state.

        Raises:
            ConnectorConfigError: If the type is not registered.
        """
        if not connector_registry.is_registered(connector_type):
            available = ", ".join(sorted(connector_registry.list_types().keys()))
            raise ConnectorConfigError(
                message=f"Unknown connector type '{connector_type}'. Available: {available}",
                details={"connector_type": connector_type, "available": available},
            )

        # Instantiate via registry
        instance = connector_registry.create(connector_type, config=config)
        cid = connector_id or f"{connector_type}-{id(instance)}"

        # Run lifecycle initialisation
        await lifecycle_manager.initialize(cid, instance)
        logger.info("Connector %s (%s) created and initialised", cid, connector_type)
        return instance

    async def create_raw(
        self,
        connector_type: str,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseConnector:
        """Create a connector instance without lifecycle initialisation.

        Use for one-off operations (e.g. connection testing) where
        lifecycle tracking is not needed.

        Args:
            connector_type: Registered type key.
            config: Connector-specific configuration.

        Returns:
            A bare (uninitialised) BaseConnector instance.
        """
        if not connector_registry.is_registered(connector_type):
            available = ", ".join(sorted(connector_registry.list_types().keys()))
            raise ConnectorConfigError(
                message=f"Unknown connector type '{connector_type}'. Available: {available}",
                details={"connector_type": connector_type, "available": available},
            )
        return connector_registry.create(connector_type, config=config)


# Module-level singleton
connector_factory = ConnectorFactory()
