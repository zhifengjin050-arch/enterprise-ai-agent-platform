"""Relation extraction package for Knowledge Graph Lite.

Extracts typed relations between entities from enterprise documents
using rule-based patterns and LLM fallback.
"""

from app.relation.models import KnowledgeRelation, RelationType
from app.relation.repository import RelationRepository

__all__ = [
    "KnowledgeRelation",
    "RelationType",
    "RelationRepository",
]
