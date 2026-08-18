"""Relation extractor with rule-based + LLM fallback.

Two-layer strategy:
1. Rule-based pattern matching for common relational patterns
2. LLM fallback for complex/ambiguous documents
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from app.relation.models import RelationType

# ── Rule patterns for relation extraction ──
# Maps keywords to (relation_type, explanation)
_RELATION_PATTERNS: Dict[str, tuple] = {
    "depends on": (RelationType.DEPENDS_ON, ""),
    "depends_on": (RelationType.DEPENDS_ON, ""),
    "依赖": (RelationType.DEPENDS_ON, ""),
    "depends": (RelationType.DEPENDS_ON, ""),
    "uses": (RelationType.USES, ""),
    "使用": (RelationType.USES, ""),
    "连接": (RelationType.USES, ""),
    "connects": (RelationType.USES, ""),
    "belongs to": (RelationType.BELONGS_TO, ""),
    "belongs_to": (RelationType.BELONGS_TO, ""),
    "属于": (RelationType.BELONGS_TO, ""),
    "caused by": (RelationType.CAUSED_BY, ""),
    "caused_by": (RelationType.CAUSED_BY, ""),
    "导致": (RelationType.CAUSED_BY, ""),
    "引起": (RelationType.CAUSED_BY, ""),
    "solved by": (RelationType.SOLVED_BY, ""),
    "solved_by": (RelationType.SOLVED_BY, ""),
    "解决": (RelationType.SOLVED_BY, ""),
    "owned by": (RelationType.OWNED_BY, ""),
    "owned_by": (RelationType.OWNED_BY, ""),
}


@dataclass
class ExtractedRelation:
    """A single extracted relation.

    Attributes:
        source: Source entity name.
        target: Target entity name.
        relation_type: Relation type string.
        confidence: Confidence score (0.0 to 1.0).
    """
    source: str = ""
    target: str = ""
    relation_type: str = ""
    confidence: float = 1.0


class RelationExtractor:
    """Extract relations between entities from document content.

    Two-layer strategy:
    1. Rule-based pattern matching for common relational phrases.
    2. LLM fallback for deeper extraction (complex docs).

    Args:
        llm_client: Optional LLM client override for testing.
    """

    def __init__(self, llm_client=None):
        if llm_client is not None:
            self._llm = llm_client
        else:
            from app.llm.client import llm_client as _llm
            self._llm = _llm

    def _rule_extract(
        self,
        entities: List[Any],
        content: str,
    ) -> List[ExtractedRelation]:
        """First-layer rule-based relation extraction.

        Args:
            entities: List of entity objects with .name attribute.
            content: Document content text.

        Returns:
            List of ExtractedRelation from pattern matching.
        """
        content_lower = content.lower()
        relations: List[ExtractedRelation] = []
        seen: set = set()

        for pattern, (rtype, _) in _RELATION_PATTERNS.items():
            if pattern not in content_lower:
                continue

            # Find sentences containing the pattern
            for sentence in content_lower.replace("\n", " ").split("。"):
                if pattern not in sentence:
                    continue

                # Find entity names in this sentence
                found_entities = [
                    e for e in entities
                    if e.name.lower() in sentence
                ]

                if len(found_entities) >= 2:
                    # First entity = source, entity after pattern = target
                    for src in found_entities:
                        pos_src = sentence.find(src.name.lower())
                        for tgt in found_entities:
                            if tgt.name.lower() == src.name.lower():
                                continue
                            pos_tgt = sentence.find(tgt.name.lower())
                            # Determine direction based on positions
                            source_name = src.name
                            target_name = tgt.name
                            key = (source_name, target_name, rtype.value)
                            if key not in seen:
                                seen.add(key)
                                relations.append(ExtractedRelation(
                                    source=source_name,
                                    target=target_name,
                                    relation_type=rtype.value,
                                    confidence=0.7,
                                ))

        return relations

    async def extract_relations(
        self,
        entities: List[Any],
        title: str,
        content: str,
        use_llm_fallback: bool = True,
    ) -> List[ExtractedRelation]:
        """Extract relations from document content.

        Args:
            entities: List of extracted entities (must have .name).
            title: Document title.
            content: Document content.
            use_llm_fallback: Whether to use LLM fallback.

        Returns:
            List of ExtractedRelation.
        """
        if not entities:
            return []

        # Layer 1: Rule-based
        rule_results = self._rule_extract(entities, content)

        if not use_llm_fallback:
            return rule_results

        # Layer 2: LLM fallback if rule yields too few
        if len(rule_results) < 3:
            try:
                from app.prompts.relation_extraction import (
                    RELATION_EXTRACTION_SCHEMA,
                    RELATION_EXTRACTION_SYSTEM_PROMPT,
                    build_relation_extraction_prompt,
                )

                prompt = build_relation_extraction_prompt(
                    title, content,
                    [{"name": e.name, "type": getattr(e, "entity_type", "")}
                     for e in entities],
                )
                result = await self._llm.structured_output(
                    prompt=prompt,
                    schema=RELATION_EXTRACTION_SCHEMA,
                    system_prompt=RELATION_EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.1,
                )

                llm_relations = result.get("relations", [])
                seen = {(r.source, r.target, r.relation_type)
                        for r in rule_results}
                merged = list(rule_results)

                for rel in llm_relations[:20]:
                    source = rel.get("source", "").strip()
                    target = rel.get("target", "").strip()
                    rtype = rel.get("type", "").strip()
                    conf = float(rel.get("confidence", 0.8))
                    key = (source, target, rtype)
                    if source and target and key not in seen:
                        seen.add(key)
                        merged.append(ExtractedRelation(
                            source=source,
                            target=target,
                            relation_type=rtype,
                            confidence=conf,
                        ))

                return merged

            except Exception as exc:
                logger.warning("LLM relation extraction failed, falling back to rules: %s", exc)

        return rule_results


async def extract_relations(
    entities: List[Any],
    title: str,
    content: str,
    llm_client=None,
) -> List[ExtractedRelation]:
    """Convenience function for relation extraction.

    Args:
        entities: List of extracted entities.
        title: Document title.
        content: Document content.
        llm_client: Optional LLM client override.

    Returns:
        List of ExtractedRelation.
    """
    extractor = RelationExtractor(llm_client=llm_client)
    return await extractor.extract_relations(entities, title, content)
