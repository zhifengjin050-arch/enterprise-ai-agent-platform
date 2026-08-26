"""Entity extraction package for Knowledge Graph Lite.

Extracts named entities from enterprise documents using
rule-based patterns and LLM fallback.
"""

from app.entity.extractor import EntityExtractor, extract_entities
from app.entity.models import EntityType, KnowledgeEntity
from app.entity.repository import EntityRepository

__all__ = [
    "KnowledgeEntity",
    "EntityType",
    "EntityRepository",
    "EntityExtractor",
    "extract_entities",
]
