"""Entity extractor with rule-based + LLM fallback.

Two-layer strategy:
1. Rule-based keyword matching for known technologies
2. LLM fallback for complex/ambiguous documents
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)

from app.entity.models import EntityType

# ── Known technology / tool keywords for rule-based extraction ──
KNOWN_ENTITIES: Dict[str, str] = {
    # Technologies
    "kubernetes": EntityType.TECHNOLOGY.value,
    "k8s": EntityType.TECHNOLOGY.value,
    "docker": EntityType.TECHNOLOGY.value,
    "redis": EntityType.TECHNOLOGY.value,
    "mysql": EntityType.TECHNOLOGY.value,
    "postgresql": EntityType.TECHNOLOGY.value,
    "postgres": EntityType.TECHNOLOGY.value,
    "mongodb": EntityType.TECHNOLOGY.value,
    "nginx": EntityType.TECHNOLOGY.value,
    "linux": EntityType.TECHNOLOGY.value,
    "python": EntityType.TECHNOLOGY.value,
    "java": EntityType.TECHNOLOGY.value,
    "go": EntityType.TECHNOLOGY.value,
    "elasticsearch": EntityType.TECHNOLOGY.value,
    "kafka": EntityType.TECHNOLOGY.value,
    "rabbitmq": EntityType.TECHNOLOGY.value,
    "prometheus": EntityType.TOOL.value,
    "grafana": EntityType.TOOL.value,
    "jenkins": EntityType.TOOL.value,
    "gitlab": EntityType.TOOL.value,
    "terraform": EntityType.TOOL.value,
    "ansible": EntityType.TOOL.value,
    "istio": EntityType.COMPONENT.value,
    "envoy": EntityType.COMPONENT.value,
    "consul": EntityType.TECHNOLOGY.value,
    "vault": EntityType.TECHNOLOGY.value,
    # Services (common naming patterns)
    "api gateway": EntityType.SERVICE.value,
    "gateway": EntityType.SERVICE.value,
    # Phase 5 Intelligence entity hints
    "rest api": EntityType.API.value,
    "graphql": EntityType.API.value,
    "openapi": EntityType.API.value,
    "microservice": EntityType.SYSTEM.value,
    "platform": EntityType.SYSTEM.value,
}


@dataclass
class ExtractedEntity:
    """A single extracted entity.

    Attributes:
        name: Entity name.
        entity_type: Entity type string.
        description: Optional description.
    """

    name: str = ""
    entity_type: str = ""
    description: str = ""


class EntityExtractor:
    """Extract entities from document content.

    Two-layer strategy:
    1. Rule-based keyword scan for known technologies/tools.
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

    def _rule_extract(self, title: str, content: str) -> List[ExtractedEntity]:
        """First-layer rule-based entity extraction.

        Args:
            title: Document title.
            content: Document content.

        Returns:
            List of ExtractedEntity from keyword matching.
        """
        text = f"{title}\n{content}".lower()
        found: Dict[str, str] = {}
        for keyword, etype in KNOWN_ENTITIES.items():
            if keyword in text:
                # Proper name: capitalize first letter
                name = keyword.capitalize()
                if name not in found:
                    found[name] = etype

        return [ExtractedEntity(name=n, entity_type=t, description="") for n, t in found.items()]

    async def extract_entities(
        self,
        title: str,
        content: str,
        use_llm_fallback: bool = True,
    ) -> List[ExtractedEntity]:
        """Extract entities from document content.

        Args:
            title: Document title.
            content: Document content text.
            use_llm_fallback: Whether to use LLM fallback.

        Returns:
            List of ExtractedEntity.
        """
        # Layer 1: Rule-based
        rule_results = self._rule_extract(title, content)

        if not use_llm_fallback:
            return rule_results

        # Layer 2: LLM fallback if rule yields too few (< 3)
        if len(rule_results) < 3:
            try:
                from app.prompts.entity_extraction import (
                    ENTITY_EXTRACTION_SCHEMA,
                    ENTITY_EXTRACTION_SYSTEM_PROMPT,
                    build_entity_extraction_prompt,
                )

                prompt = build_entity_extraction_prompt(title, content)
                result = await self._llm.structured_output(
                    prompt=prompt,
                    schema=ENTITY_EXTRACTION_SCHEMA,
                    system_prompt=ENTITY_EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.1,
                )

                llm_entities = result.get("entities", [])
                seen = {e.name.lower() for e in rule_results}
                merged = list(rule_results)

                for ent in llm_entities[:20]:
                    name = ent.get("name", "").strip()
                    etype = ent.get("type", "").strip()
                    desc = ent.get("description", "").strip()
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        merged.append(
                            ExtractedEntity(
                                name=name,
                                entity_type=etype,
                                description=desc,
                            )
                        )

                return merged

            except Exception as exc:
                logger.warning("LLM entity extraction failed, falling back to rules: %s", exc)

        return rule_results


async def extract_entities(
    title: str,
    content: str,
    llm_client=None,
) -> List[ExtractedEntity]:
    """Convenience function for entity extraction.

    Args:
        title: Document title.
        content: Document content.
        llm_client: Optional LLM client override.

    Returns:
        List of ExtractedEntity.
    """
    extractor = EntityExtractor(llm_client=llm_client)
    return await extractor.extract_entities(title, content)
