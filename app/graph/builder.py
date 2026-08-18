"""Entity-relation graph builder from document content.

Constructs knowledge entities and relations from extracted
entity/relation data and persists them via repositories.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from app.entity.extractor import EntityExtractor
from app.entity.repository import EntityRepository
from app.relation.extractor import RelationExtractor
from app.relation.repository import RelationRepository


class GraphBuilder:
    """Build and persist a knowledge graph from a document.

    Orchestrates entity extraction → relation extraction →
    repository persistence in a single pipeline.

    Args:
        entity_repo: Optional EntityRepository override.
        relation_repo: Optional RelationRepository override.
        llm_client: Optional LLM client override.
    """

    def __init__(
        self,
        entity_repo: Optional[EntityRepository] = None,
        relation_repo: Optional[RelationRepository] = None,
        llm_client=None,
    ):
        self._entity_repo = entity_repo
        self._relation_repo = relation_repo
        self._llm_client = llm_client

    async def build_from_document(
        self,
        title: str,
        content: str,
        session=None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract entities + relations from a document and persist.

        Args:
            title: Document title.
            content: Document markdown content.
            session: AsyncSession for repository operations.
            document_id: Optional originating document ID.

        Returns:
            Dict with 'entities' and 'relations' lists.
        """
        # Step 1: Extract entities
        entity_extractor = EntityExtractor(llm_client=self._llm_client)
        extracted_entities = await entity_extractor.extract_entities(
            title, content,
        )

        # Step 2: Extract relations
        relation_extractor = RelationExtractor(llm_client=self._llm_client)
        extracted_relations = await relation_extractor.extract_relations(
            extracted_entities, title, content,
        )

        # Step 3: Persist if session is available
        entity_records: list = []
        relation_records: list = []

        if session is not None:
            repo_entity = self._entity_repo or EntityRepository(session)
            repo_relation = self._relation_repo or RelationRepository(session)
            name_to_id: Dict[str, str] = {}

            for ee in extracted_entities:
                try:
                    entity = await repo_entity.create_entity(
                        name=ee.name,
                        entity_type=ee.entity_type,
                        description=ee.description,
                        metadata_json={
                            "source_document_id": document_id,
                        } if document_id else {},
                    )
                    entity_records.append(entity)
                    name_to_id[ee.name.lower()] = str(entity.id)
                except Exception as exc:
                    logger.warning("Entity creation failed, trying lookup by name: %s", exc)
                    existing = await repo_entity.find_by_name(ee.name)
                    if existing:
                        entity_records.append(existing[0])
                        name_to_id[ee.name.lower()] = str(existing[0].id)

            for er in extracted_relations:
                src_id = name_to_id.get(er.source.lower())
                tgt_id = name_to_id.get(er.target.lower())
                if src_id and tgt_id:
                    try:
                        relation = await repo_relation.create_relation(
                            source_entity_id=src_id,
                            target_entity_id=tgt_id,
                            relation_type=er.relation_type,
                            confidence=er.confidence,
                            source_document_id=document_id,
                        )
                        relation_records.append(relation)
                    except Exception as exc:
                        logger.warning("Relation creation failed: %s", exc)

        return {
            "entities": entity_records or extracted_entities,
            "relations": relation_records or extracted_relations,
        }
