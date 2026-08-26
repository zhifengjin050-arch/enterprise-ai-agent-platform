"""
Knowledge source abstract interface.

Defines the base contract for all document loaders.
Any new knowledge source (Notion, Confluence, Database, etc.)
should implement KnowledgeLoader to be compatible with the system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Document:
    """Represents a single document loaded from a knowledge source."""

    content: str
    metadata: dict = field(default_factory=dict)
    source: Optional[str] = None


class KnowledgeLoader(ABC):
    """Abstract base class for all knowledge source loaders.

    Subclasses must implement:
        - load_documents(): Load and return all documents from the source.
        - get_source_name(): Return a human-readable name for the source.
    """

    @abstractmethod
    def load_documents(self) -> List[Document]: ...

    @abstractmethod
    def get_source_name(self) -> str: ...

    def validate_connection(self) -> bool:
        """Optional: Validate connectivity to the knowledge source."""
        return True
