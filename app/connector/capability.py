"""Connector capability system.

Each connector declares its capabilities at the class level, enabling
the registry and API layer to query what operations are supported.

Capabilities:
    DOCUMENT_READ:      Can read/list documents from the source.
    DOCUMENT_WRITE:     Can write/create documents in the source.
    SEARCH:             Can search documents via the source's search API.
    WEBHOOK:            Can receive webhook event notifications.
    INCREMENTAL_SYNC:   Supports incremental/delta sync (cursor-based).
    FULL_SYNC:          Supports full (all documents) sync.
"""

from __future__ import annotations

import enum


class ConnectorCapability(str, enum.Enum):
    """Enumeration of connector capabilities."""

    DOCUMENT_READ = "document_read"
    DOCUMENT_WRITE = "document_write"
    SEARCH = "search"
    WEBHOOK = "webhook"
    INCREMENTAL_SYNC = "incremental_sync"
    FULL_SYNC = "full_sync"
