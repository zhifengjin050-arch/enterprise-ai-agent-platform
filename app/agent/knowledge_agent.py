"""Conversational Knowledge Agent.

End-to-end pipeline for enterprise knowledge Q&A:

  1. Intent classification (rule + LLM fallback)
  2. Query rewriting (synonym expansion + LLM fallback)
  3. Hybrid search (full-text + semantic via RRF)
  4. Context building (dedup, token-limit)
  5. Answer generation (LLM structured output)
  6. Citation extraction
  7. Conversation memory update

Output: KnowledgeAgentResult with answer, citations, confidence, sources.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agent.answer_generator import AnswerGenerator
from app.citation.extractor import CitationExtractor
from app.citation.models import CitationSource
from app.conversation.memory import memory as conversation_memory
from app.query.builder import ContextBuilder
from app.query.intent import classify_intent
from app.query.rewrite import QueryRewriteService
from app.search.hybrid import HybridSearch, get_hybrid_search


@dataclass
class KnowledgeAgentResult:
    """Result from the knowledge agent.

    Attributes:
        answer: Generated answer text.
        citations: List of citation sources.
        confidence: Overall confidence score.
        sources: Unique source titles used.
        conversation_id: Conversation session ID.
        intent: Recognized query intent.
    """

    answer: str = ""
    citations: List[CitationSource] = field(default_factory=list)
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    conversation_id: str = ""
    intent: str = "general_search"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": round(self.confidence, 3),
            "sources": self.sources,
            "conversation_id": self.conversation_id,
            "intent": self.intent,
        }


class KnowledgeAgent:
    """End-to-end conversational knowledge agent.

    Orchestrates the full Q&A pipeline from natural language query
    to structured answer with citations.

    Args:
        llm_client: Optional LLM client override for testing.
        hybrid_search: Optional HybridSearch override for testing.
    """

    def __init__(
        self,
        llm_client=None,
        hybrid_search: Optional[HybridSearch] = None,
    ):
        self._llm_client = llm_client
        self._hybrid_search = hybrid_search
        self._intent_cache: Dict[str, str] = {}

    async def ask(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        user_id: str = "",
        use_llm_fallback: bool = True,
    ) -> KnowledgeAgentResult:
        """Process a user query through the full knowledge pipeline.

        Args:
            query: User's natural language question.
            conversation_id: Existing conversation ID for history.
            user_id: Optional user identifier.
            use_llm_fallback: Whether to allow LLM fallback.

        Returns:
            KnowledgeAgentResult with answer, citations, confidence.
        """
        # Step 0: Ensure conversation
        conv_id = conversation_id or str(uuid.uuid4())
        conv = conversation_memory.get_conversation(conv_id)
        if conv is None:
            conv = conversation_memory.create_conversation(
                conversation_id=conv_id,
                user_id=user_id,
                title=query[:80],
            )

        # Save user message
        conversation_memory.add_message(conv_id, "user", query)

        # Step 1: Intent classification
        intent_obj = classify_intent(
            query,
            use_llm_fallback=use_llm_fallback,
            llm_client=self._llm_client,
        )
        self._intent_cache[conv_id] = intent_obj.intent

        # Step 2: Query rewriting
        rewrite_service = QueryRewriteService(llm_client=self._llm_client)
        rewrite_result = await rewrite_service.rewrite(
            query=query,
            intent=intent_obj.intent,
        )
        all_queries = rewrite_result.rewritten_queries or [query]

        # Step 2.5: Graph Expansion (Knowledge Graph Lite)
        # Extract entity names from the query and find related entities
        graph_terms: List[str] = []
        try:
            from app.entity.extractor import EntityExtractor
            entity_extractor = EntityExtractor(llm_client=self._llm_client)
            query_entities = entity_extractor._rule_extract(query, "")
            if query_entities:
                # Add neighbor name queries via graph traversal
                from app.db.session import get_session_factory
                from app.entity.repository import EntityRepository
                from app.relation.repository import RelationRepository
                factory = get_session_factory()
                async with factory() as session:
                    entity_repo = EntityRepository(session)
                    relation_repo = RelationRepository(session)
                    for ent in query_entities:
                        matches = await entity_repo.find_by_name(ent.name, exact=False)
                        for match in matches:
                            graph_data = await relation_repo.get_entity_graph(str(match.id))
                            for neighbor in graph_data.get("neighbors", {}).values():
                                if hasattr(neighbor, "name"):
                                    graph_terms.append(neighbor.name)
        except Exception as exc:
            logger.warning("Graph expansion failed (best-effort): %s", exc)

        # Merge graph-expanded terms into queries
        all_queries.extend(graph_terms)

        # Step 3: Hybrid search
        hs = self._hybrid_search or get_hybrid_search()
        all_results: List[Any] = []
        seen_ids: set = set()
        for q in all_queries:
            results = await hs.search(query=q, top_k=10)
            for r in results:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    all_results.append(r)

        # Sort by score descending
        all_results.sort(key=lambda r: r.score, reverse=True)
        all_results = all_results[:20]

        # Step 4: Build context
        builder = ContextBuilder(max_tokens=12000)
        context_docs = builder.build(all_results)
        context_text = builder.to_text(context_docs)

        # Step 5: Get conversation history
        history_text = conversation_memory.to_prompt_context(conv_id)

        # Step 6: Generate answer
        generator = AnswerGenerator(llm_client=self._llm_client)
        answer_result = await generator.generate(
            query=query,
            context_text=context_text,
            history_text=history_text,
        )

        # Step 7: Extract citations
        extractor = CitationExtractor()
        citations = extractor.extract(
            all_results,
            max_sources=5,
        )

        # Step 8: Save assistant message
        conversation_memory.add_message(conv_id, "assistant", answer_result.answer)

        # Build source list
        sources = list(dict.fromkeys(
            c.title for c in citations if c.title
        ))

        return KnowledgeAgentResult(
            answer=answer_result.answer,
            citations=citations,
            confidence=answer_result.confidence,
            sources=sources,
            conversation_id=conv_id,
            intent=intent_obj.intent,
        )
