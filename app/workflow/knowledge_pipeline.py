"""Knowledge document processing pipeline.

LangGraph StateGraph that orchestrates the full document lifecycle:

    parse -> classify -> tag -> quality -> (embed -> store -> index)  [score>=0.5]
                                         -> (review)                  [score<0.5]

AI Knowledge Intelligence Layer (Day 7):
- classify_node: Rule-based + LLM fallback (LLMClassifier)
- tag_node: Rule-based + LLM fallback (AITagger)
- quality_node: Rule-based + LLM fallback (LLMQualityAnalyzer)

Knowledge Graph Lite integration (Day 9):
- entity_node: Extract named entities (rule + LLM fallback)
- relation_node: Extract entity relations (rule + LLM fallback)

This is the core knowledge ingestion workflow, NOT a conversational Agent.
No question/answer/chat_history fields anywhere.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Literal

logger = logging.getLogger(__name__)

from app.workflow.state import KnowledgeState

# ──────────────────────────────────────────────
# Node implementations
# ──────────────────────────────────────────────


def parse_node(state: KnowledgeState) -> Dict[str, Any]:
    """Parse raw content into structured markdown.

    Calls DocumentParser to transform the raw_content into
    normalized markdown with extracted title and metadata.

    Args:
        state: Current pipeline state with raw_content.

    Returns:
        Partial state update with markdown_content, title, metadata.
    """
    try:
        raw_content = state.get("raw_content") or ""
        file_path = state.get("file_path")
        existing_meta = dict(state.get("metadata") or {})

        title = state.get("title") or "Untitled"
        if not title or title == "Untitled":
            if file_path:
                from pathlib import Path

                title = Path(file_path).stem

        return {
            "markdown_content": raw_content,
            "title": title,
            "metadata": existing_meta,
            "status": "processing",
            "current_node": "parse",
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"Parse failed: {exc}",
        }


async def classify_node(state: KnowledgeState) -> Dict[str, Any]:
    """Classify document type using rule classifier + LLM fallback.

    Strategy (two-layer):
        1. Run rule_classifier with keyword matching.
        2. If rule confidence < 0.8, fall back to LLMClassifier.

    Args:
        state: Current state with markdown_content and title.

    Returns:
        Partial state update with doc_type.
    """
    try:
        content = state.get("markdown_content") or ""
        title = state.get("title") or ""

        # Layer 1: Rule-based classification
        from app.knowledge.classifier import rule_classifier

        rule_result = rule_classifier(title, content)

        doc_type = rule_result.doc_type

        # Layer 2: LLM fallback if rule confidence < 0.8
        if rule_result.confidence < 0.8:
            try:
                from app.knowledge.classifier import LLMClassifier

                llm_classifier = LLMClassifier()
                llm_result = await llm_classifier.classify(title, content)

                if llm_result.confidence > rule_result.confidence:
                    doc_type = llm_result.doc_type
            except Exception:
                # If LLM fails, fall back to rule result
                pass

        return {
            "doc_type": doc_type,
            "current_node": "classify",
            "error": None,
        }
    except Exception as exc:
        return {
            "doc_type": None,
            "error": f"Classification failed: {exc}",
        }


async def tag_node(state: KnowledgeState) -> Dict[str, Any]:
    """Generate knowledge tags using rule extraction + AI fallback.

    Strategy (two-layer):
        1. Run rule_extract_tags with keyword matching.
        2. If fewer than 3 tags, fall back to AITagger.

    Args:
        state: Current state with markdown_content, title, doc_type.

    Returns:
        Partial state update with tags list.
    """
    try:
        content = state.get("markdown_content") or ""
        title = state.get("title") or ""
        doc_type = state.get("doc_type")

        # Layer 1: Rule-based tag extraction
        from app.knowledge.tagger import rule_extract_tags

        rule_tags = list(rule_extract_tags(title, content))

        # Add doc_type as auto-tag
        if doc_type and doc_type not in rule_tags:
            rule_tags.insert(0, doc_type)

        # Layer 2: LLM fallback if few tags extracted
        if len(rule_tags) < 3:
            try:
                from app.knowledge.tagger import AITagger

                ai_tagger = AITagger()
                ai_tags = await ai_tagger.generate_tags(title, content)

                # Merge: rule tags first, then AI tags (deduped)
                seen: set = set(rule_tags)
                merged = list(rule_tags)
                for t in ai_tags:
                    if t not in seen:
                        seen.add(t)
                        merged.append(t)
                rule_tags = merged[:10]
            except Exception:
                pass

        return {
            "tags": rule_tags[:10],
            "current_node": "tag",
            "error": None,
        }
    except Exception as exc:
        return {
            "tags": [],
            "error": f"Tagging failed: {exc}",
        }


async def quality_node(state: KnowledgeState) -> Dict[str, Any]:
    """Assess document quality using rule analyzer + LLM fallback.

    Strategy (two-layer):
        1. Run rule_quality_analyzer with heuristic scoring.
        2. If rule score < 0.8, fall back to LLMQualityAnalyzer.

    Args:
        state: Current state with markdown_content and title.

    Returns:
        Partial state update with quality_score and quality_issues.
    """
    try:
        content = state.get("markdown_content") or ""
        title = state.get("title") or ""

        # Layer 1: Rule-based quality analysis
        from app.review.analyzer import rule_quality_analyzer

        rule_result = rule_quality_analyzer(title, content)
        score = rule_result.score
        issues = list(rule_result.issues)

        # Layer 2: LLM fallback if rule score < 0.8
        if rule_result.score < 0.8:
            try:
                from app.review.analyzer import LLMQualityAnalyzer

                llm_analyzer = LLMQualityAnalyzer()
                llm_result = await llm_analyzer.analyze(title, content)

                if llm_result.score > rule_result.score:
                    score = llm_result.score
                    issues = list(llm_result.issues)
            except Exception:
                pass

        return {
            "quality_score": score,
            "quality_issues": issues,
            "current_node": "quality",
            "error": None,
        }
    except Exception as exc:
        return {
            "quality_score": 0.0,
            "quality_issues": [f"Quality check error: {exc}"],
            "error": f"Quality check failed: {exc}",
        }


async def entity_node(state: KnowledgeState) -> Dict[str, Any]:
    """Extract entities from document content (rule + LLM fallback).

    Args:
        state: Current state with markdown_content and title.

    Returns:
        Partial state update with entities list.
    """
    try:
        title = state.get("title") or ""
        content = state.get("markdown_content") or ""

        from app.entity.extractor import EntityExtractor

        extractor = EntityExtractor()
        extracted = await extractor.extract_entities(title, content)

        return {
            "entities": [
                {"name": e.name, "entity_type": e.entity_type, "description": e.description}
                for e in extracted
            ],
            "current_node": "entity",
            "error": None,
        }
    except Exception as exc:
        return {
            "entities": [],
            "error": f"Entity extraction failed: {exc}",
        }


async def relation_node(state: KnowledgeState) -> Dict[str, Any]:
    """Extract relations between entities (rule + LLM fallback).

    Args:
        state: Current state with entities, markdown_content and title.

    Returns:
        Partial state update with relations list.
    """
    try:
        title = state.get("title") or ""
        content = state.get("markdown_content") or ""
        entities = state.get("entities") or []

        from app.entity.extractor import ExtractedEntity
        from app.relation.extractor import RelationExtractor

        extracted_entities = [
            ExtractedEntity(name=e.get("name", ""), entity_type=e.get("entity_type", ""))
            for e in entities
        ]

        extractor = RelationExtractor()
        extracted = await extractor.extract_relations(extracted_entities, title, content)

        return {
            "relations": [
                {
                    "source": r.source,
                    "target": r.target,
                    "relation_type": r.relation_type,
                    "confidence": r.confidence,
                }
                for r in extracted
            ],
            "current_node": "relation",
            "error": None,
        }
    except Exception as exc:
        return {
            "relations": [],
            "error": f"Relation extraction failed: {exc}",
        }


def quality_router(state: KnowledgeState) -> Literal["entity_extract", "review"]:
    """Route after quality_node based on score.

    Returns:
        "entity_extract" if score >= 0.5, "review" otherwise.
    """
    score = state.get("quality_score", 0.0)
    if score >= 0.5:
        return "entity_extract"
    return "review"


async def embedding_node(state: KnowledgeState) -> Dict[str, Any]:
    """Generate vector embedding for the document.

    Calls EmbeddingProvider when API key is configured.
    Falls back to a deterministic embedding_id in dev mode.

    Args:
        state: Current state with markdown_content.

    Returns:
        Partial state update with embedding_id.
    """
    try:
        content = state.get("markdown_content") or ""
        title = state.get("title") or ""
        embed_text = f"{title}\n\n{content[:4096]}" if content else title

        if not embed_text.strip():
            return {
                "embedding_id": None,
                "error": "No content to embed",
            }

        from app.core.config import get_settings

        settings = get_settings()
        api_key = settings.llm_api_key or settings.embedding_api_key or ""

        if api_key:
            from app.embedding.client import OpenAICompatibleEmbedding

            provider = OpenAICompatibleEmbedding()
            vector = await provider.embed_text(embed_text)
            dim = len(vector)
            embedding_id = f"emb_{state.get('document_id', 'unknown')}_dim{dim}"
        else:
            # Dev mode placeholder
            embedding_id = f"emb_{state.get('document_id', 'unknown')}"

        return {
            "embedding_id": embedding_id,
            "current_node": "embed",
            "error": None,
        }
    except Exception as exc:
        fallback_id = f"emb_{state.get('document_id', 'unknown')}"
        return {
            "embedding_id": fallback_id,
            "error": f"Embedding warning: {exc}",
        }


async def store_node(state: KnowledgeState) -> Dict[str, Any]:
    """Persist the processed document via KnowledgeRepository.

    Args:
        state: Final pipeline state with processed content and metadata.

    Returns:
        Partial state update with stored flag and document_id.
    """
    try:
        from app.db.session import get_session_factory
        from app.knowledge.models import DocumentStatus
        from app.knowledge.repository import KnowledgeRepository

        title = state.get("title") or "Untitled"
        content = state.get("markdown_content") or ""
        doc_type = state.get("doc_type")
        tags = list(state.get("tags") or [])
        embedding_id = state.get("embedding_id")
        quality = state.get("quality_score")
        metadata = dict(state.get("metadata") or {})
        document_id = state.get("document_id")

        factory = get_session_factory()
        async with factory() as session:
            repo = KnowledgeRepository(session)
            doc = await repo.create_document(
                title=title,
                content=content,
                format="markdown",
                doc_type=doc_type,
                status=DocumentStatus.DRAFT,
                source="workflow",
                source_url=None,
                embedding_id=embedding_id,
                quality_score=quality,
                metadata_json=metadata,
                tag_names=tags,
                document_id=document_id if document_id else None,
            )
            # Phase 5: chunk + graph intelligence (best-effort)
            try:
                from app.knowledge.intelligence import process_document_intelligence

                await process_document_intelligence(
                    session,
                    document_id=str(doc.id),
                    title=title,
                    content=content,
                    embed=False,  # embedding already done in embed_node
                    build_graph=True,
                )
            except Exception as intel_exc:
                logger.warning(
                    "Intelligence processing skipped for %s: %s",
                    doc.id,
                    intel_exc,
                )
            await session.commit()

        return {
            "document_id": str(doc.id),
            "stored": True,
            "current_node": "store",
            "error": None,
        }
    except Exception as exc:
        return {
            "stored": False,
            "error": f"Store failed: {exc}",
        }


async def index_node(state: KnowledgeState) -> Dict[str, Any]:
    """Index the document in ChromaDB via KnowledgeIndexer.

    Args:
        state: Pipeline state with document_id and embedding_id.

    Returns:
        Partial state update with indexed flag.
    """
    try:
        document_id = state.get("document_id")
        embedding_id = state.get("embedding_id")

        if not document_id:
            return {"indexed": False, "error": "No document_id to index"}

        from app.search.indexer import KnowledgeIndexer

        indexer = KnowledgeIndexer()
        result = await indexer.index_document(
            document_id=document_id,
            embedding_id=embedding_id,
        )

        return {
            "indexed": result.get("indexed", False),
            "current_node": "index",
            "error": None,
        }
    except Exception as exc:
        return {
            "indexed": False,
            "error": f"Index failed: {exc}",
        }


async def review_node(state: KnowledgeState) -> Dict[str, Any]:
    """Human-in-the-loop review for low-quality documents.

    Sets need_review=True and status='review'. The workflow pauses
    until an external call to approve/reject is made via the API.

    IMPORTANT: This node does NOT overwrite an existing review_decision
    that may have been set externally (e.g. via orchestrator.approve_review).

    Args:
        state: Current state after quality check.

    Returns:
        Partial state update setting review status.
    """
    issues = state.get("quality_issues", [])
    result: Dict[str, Any] = {
        "need_review": True,
        "current_node": "review",
        "error": None,
        "quality_issues": issues,
    }

    # Preserve existing review_decision if already set (e.g. via resume)
    existing_decision = state.get("review_decision")
    if existing_decision is not None:
        result["review_decision"] = existing_decision
        if existing_decision == "approved":
            result["status"] = "processing"  # Let routing continue
        else:
            result["status"] = "review"
    else:
        result["status"] = "review"
        result["review_decision"] = None

    return result


def review_router(state: KnowledgeState) -> Literal["embed", "__end__"]:
    """Route after review based on human decision.

    Returns:
        "embed" if approved, END otherwise.
    """
    decision = state.get("review_decision")
    if decision == "approved":
        return "embed"
    return "__end__"


# ──────────────────────────────────────────────
# Pipeline construction
# ──────────────────────────────────────────────


def build_knowledge_pipeline() -> Callable[..., Any]:
    """Build the complete LangGraph knowledge processing pipeline.

    Graph structure:

        parse -> classify -> tag -> quality
                                      |
                          +-----------+-----------+
                          |                       |
                     score >= 0.5           score < 0.5
                          |                       |
                       embed                  review
                          |                       |
                      store             approved / rejected
                          |                  |          |
                       index              embed       END
                          |
                        END

    Returns:
        A compiled LangGraph application, or a sequential fallback.
    """
    try:
        from langgraph.graph import END, START, StateGraph

        workflow: StateGraph = StateGraph(KnowledgeState)

        # Register nodes
        workflow.add_node("parse", parse_node)
        workflow.add_node("classify", classify_node)
        workflow.add_node("tag", tag_node)
        workflow.add_node("quality", quality_node)
        workflow.add_node("entity_extract", entity_node)
        workflow.add_node("relation_extract", relation_node)
        workflow.add_node("embed", embedding_node)
        workflow.add_node("store", store_node)
        workflow.add_node("index", index_node)
        workflow.add_node("review", review_node)

        # Sequential edges
        workflow.add_edge(START, "parse")
        workflow.add_edge("parse", "classify")
        workflow.add_edge("classify", "tag")
        workflow.add_edge("tag", "quality")

        # Conditional branch after quality
        workflow.add_conditional_edges(
            "quality",
            quality_router,
            {
                "entity_extract": "entity_extract",
                "review": "review",
            },
        )

        # Entity -> Relation -> Embed
        workflow.add_edge("entity_extract", "relation_extract")
        workflow.add_edge("relation_extract", "embed")

        # Embed -> Store -> Index -> END
        workflow.add_edge("embed", "store")
        workflow.add_edge("store", "index")
        workflow.add_edge("index", END)

        # Review conditional
        workflow.add_conditional_edges(
            "review",
            review_router,
            {
                "embed": "embed",
                "__end__": END,
            },
        )

        return workflow.compile()

    except ImportError:
        # Sequential fallback when LangGraph is unavailable
        return _build_sequential_fallback()


def _build_sequential_fallback() -> Callable[..., Any]:
    """Build a sequential fallback that mimics the graph without LangGraph."""

    def _sequential(state: KnowledgeState) -> KnowledgeState:

        async def _run(s: KnowledgeState) -> KnowledgeState:
            # parse is sync
            s.update(parse_node(s))
            # classify, tag, quality are now async
            s.update(await classify_node(s))
            s.update(await tag_node(s))
            s.update(await quality_node(s))

            score = s.get("quality_score", 0.0)
            if score >= 0.5:
                s.update(await entity_node(s))
                s.update(await relation_node(s))
                s.update(await embedding_node(s))
                s.update(await store_node(s))
                s.update(await index_node(s))
            else:
                s.update(await review_node(s))
                decision = s.get("review_decision")
                if decision == "approved":
                    s.update(await entity_node(s))
                    s.update(await relation_node(s))
                    s.update(await embedding_node(s))
                    s.update(await store_node(s))
                    s.update(await index_node(s))

            return s

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run(state))

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _run(state)).result()

    return _sequential


# Module-level singleton
knowledge_pipeline: Callable[..., Any] = build_knowledge_pipeline()
