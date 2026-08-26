"""Connector registry — factory for creating connector instances.

The registry maps connector type strings (e.g., "feishu", "yuque", "gitlab")
to their corresponding adapter classes, enabling dynamic instantiation
from configuration.

Enterprise features:
    - Auto-registration: connectors call `register()` at class level.
    - Metadata & capability querying: inspect registered connectors.
    - Version management: check connector adapter versions.
    - Dynamic discovery: find connectors that support specific capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from app.connector.base import BaseConnector
from app.connector.capability import ConnectorCapability

logger = logging.getLogger(__name__)


def _default_metadata(adapter_cls: Type[BaseConnector]) -> Dict[str, Any]:
    """Extract static metadata from a connector class without instantiating it.

    Args:
        adapter_cls: The connector class.

    Returns:
        Dict with name, type, version, description, features, capabilities, config_schema.
    """
    capabilities = getattr(adapter_cls, "capabilities", [])
    features = getattr(adapter_cls, "features", [])
    config_schema = getattr(adapter_cls, "config_schema", {})

    return {
        "name": getattr(adapter_cls, "name", "unknown"),
        "type": getattr(adapter_cls, "connector_type", "unknown"),
        "version": getattr(adapter_cls, "version", "0.1.0"),
        "author": getattr(adapter_cls, "author", ""),
        "description": getattr(adapter_cls, "description", ""),
        "features": features,
        "capabilities": [c.value for c in capabilities] if capabilities else [],
        "config_schema": config_schema,
    }


class ConnectorRegistry:
    """Registry of available connector types.

    Connectors register themselves with a type key, and the registry
    creates instances on demand based on configuration.

    New enterprise methods:
        - get_metadata(type) → metadata dict
        - list_capabilities(type) → list of capability values
        - get_version(type) → version string
        - check_support(type, capability) → bool
        - discover(capability) → matching connector types
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, Type[BaseConnector]] = {}

    def register(
        self,
        connector_type: str,
        adapter_class: Type[BaseConnector],
    ) -> None:
        """Register a connector adapter class.

        Args:
            connector_type: Type key (e.g., "feishu", "yuque").
            adapter_class: The connector class (must subclass BaseConnector).

        Raises:
            ValueError: If connector_type is already registered.
            TypeError: If adapter_class does not subclass BaseConnector.
        """
        if connector_type in self._adapters:
            raise ValueError(f"Connector type '{connector_type}' is already registered")
        if not issubclass(adapter_class, BaseConnector):
            raise TypeError(f"Adapter must subclass BaseConnector, got {adapter_class}")
        self._adapters[connector_type] = adapter_class
        logger.info("Registered connector type '%s' (%s)", connector_type, adapter_class.__name__)

    def unregister(self, connector_type: str) -> None:
        """Unregister a connector type.

        Args:
            connector_type: Type key to remove.
        """
        removed = self._adapters.pop(connector_type, None)
        if removed:
            logger.info("Unregistered connector type '%s'", connector_type)

    def create(
        self,
        connector_type: str,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseConnector:
        """Create a connector instance of the given type.

        Args:
            connector_type: Type key.
            config: Configuration dict for the connector.

        Returns:
            A BaseConnector instance.

        Raises:
            ValueError: If connector_type is not registered.
        """
        if connector_type not in self._adapters:
            available = ", ".join(sorted(self._adapters.keys()))
            raise ValueError(f"Unknown connector type: '{connector_type}'. Available: {available}")
        adapter_cls = self._adapters[connector_type]
        return adapter_cls(config=config)

    def list_types(self) -> Dict[str, str]:
        """List all registered connector types with their names.

        Returns:
            Dict mapping type key to class-level name.
        """
        return {key: getattr(cls, "name", key) for key, cls in self._adapters.items()}

    def is_registered(self, connector_type: str) -> bool:
        """Check if a connector type is registered.

        Args:
            connector_type: Type key.

        Returns:
            True if registered.
        """
        return connector_type in self._adapters

    # ── Enterprise metadata / capability methods ──

    def get_metadata(self, connector_type: str) -> Dict[str, Any]:
        """Get static metadata for a registered connector type.

        Args:
            connector_type: Type key.

        Returns:
            Metadata dict (name, type, version, description, features, etc.).

        Raises:
            ValueError: If connector_type is not registered.
        """
        if connector_type not in self._adapters:
            raise ValueError(f"Unknown connector type: '{connector_type}'")
        return _default_metadata(self._adapters[connector_type])

    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all registered connector types.

        Returns:
            Dict mapping type key to metadata dict.
        """
        return {key: _default_metadata(cls) for key, cls in self._adapters.items()}

    def list_capabilities(self, connector_type: str) -> List[str]:
        """List the capabilities declared by a connector type.

        Args:
            connector_type: Type key.

        Returns:
            List of capability strings (e.g., ["document_read", "search"]).

        Raises:
            ValueError: If connector_type is not registered.
        """
        if connector_type not in self._adapters:
            raise ValueError(f"Unknown connector type: '{connector_type}'")
        cls = self._adapters[connector_type]
        caps: List[ConnectorCapability] = getattr(cls, "capabilities", [])
        return [c.value for c in caps]

    def get_version(self, connector_type: str) -> str:
        """Get the version string for a registered connector type.

        Args:
            connector_type: Type key.

        Returns:
            Version string (e.g., "1.0.0").

        Raises:
            ValueError: If connector_type is not registered.
        """
        if connector_type not in self._adapters:
            raise ValueError(f"Unknown connector type: '{connector_type}'")
        return getattr(self._adapters[connector_type], "version", "0.1.0")

    def check_support(self, connector_type: str, capability: str | ConnectorCapability) -> bool:
        """Check if a connector type supports a specific capability.

        Args:
            connector_type: Type key.
            capability: Capability string or ConnectorCapability enum value.

        Returns:
            True if the connector declares the capability.

        Raises:
            ValueError: If connector_type is not registered.
        """
        if isinstance(capability, ConnectorCapability):
            capability = capability.value
        if connector_type not in self._adapters:
            raise ValueError(f"Unknown connector type: '{connector_type}'")
        cls = self._adapters[connector_type]
        caps: List[ConnectorCapability] = getattr(cls, "capabilities", [])
        return any(c.value == capability for c in caps)

    def discover(self, capability: str | ConnectorCapability) -> List[str]:
        """Discover connector types that support a given capability.

        Args:
            capability: Capability string or ConnectorCapability enum value.

        Returns:
            List of connector type keys that declare the capability.
        """
        if isinstance(capability, ConnectorCapability):
            capability = capability.value
        result: List[str] = []
        for key, cls in self._adapters.items():
            caps: List[ConnectorCapability] = getattr(cls, "capabilities", [])
            if any(c.value == capability for c in caps):
                result.append(key)
        return result


# Module-level singleton registry
connector_registry = ConnectorRegistry()
