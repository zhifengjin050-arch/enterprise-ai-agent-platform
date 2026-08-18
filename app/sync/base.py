"""Sync engine abstract interface.

Defines the base contract for all knowledge source synchronizers.
Extends KnowledgeLoader with sync-specific operations.
"""

from abc import abstractmethod
from datetime import datetime
from typing import List, Optional

from app.knowledge.base import Document, KnowledgeLoader


class SyncEngine(KnowledgeLoader):
    """Abstract base class for knowledge source sync engines.

    Extends KnowledgeLoader with:
        - sync(): Perform full synchronization
        - incremental_sync(): Sync only changed documents
        - get_last_sync_time(): Get last sync timestamp
    """

    @abstractmethod
    def sync(self) -> List[Document]:
        """Perform full synchronization from the source.

        Returns:
            List of synced documents.
        """
        ...

    @abstractmethod
    def incremental_sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Sync only documents changed since last sync.

        Args:
            since: Only fetch documents updated after this time.

        Returns:
            List of newly synced documents.
        """
        ...

    @abstractmethod
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful sync.

        Returns:
            Datetime of last sync, or None if never synced.
        """
        ...
