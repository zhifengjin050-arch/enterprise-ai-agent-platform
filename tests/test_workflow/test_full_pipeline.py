"""End-to-end tests for the full knowledge pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflow.knowledge_pipeline import build_knowledge_pipeline


@pytest.mark.asyncio
async def test_full_pipeline_high_quality() -> None:
    """High-quality document should complete: parse → classify → tag → quality → embed → store → index."""
    state = {
        "document_id": "doc-001",
        "raw_content": (
            "# Kubernetes Deployment SOP\n\n"
            "## Prerequisites\n\n"
            "- Kubernetes cluster 1.28+\n"
            "- kubectl configured\n\n"
            "## Procedure\n\n"
            "1. Apply namespace\n"
            "2. Deploy resources\n"
            "3. Verify health\n\n"
            "## Rollback\n\n"
            "If deployment fails, run rollback script.\n"
        ),
        "title": "Kubernetes Deployment SOP",
    }

    pipeline = build_knowledge_pipeline()

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "stored-uuid-001"
    mock_repo.create_document = AsyncMock(return_value=mock_doc)
    mock_indexer = MagicMock()
    mock_indexer.index_document = AsyncMock(return_value={"indexed": True, "embedding_id": "emb_doc-001"})

    # Patch SOURCE modules (lazy imports inside node function bodies)
    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository", return_value=mock_repo),
        patch("app.search.indexer.KnowledgeIndexer", return_value=mock_indexer),
    ):
        mock_settings.return_value.llm_api_key = ""
        mock_settings.return_value.embedding_api_key = ""

        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        if hasattr(pipeline, "ainvoke"):
            result = await pipeline.ainvoke(state)
        else:
            result = pipeline(state)

    assert isinstance(result, dict)
    assert result.get("error") is None or result.get("error") == ""
    assert result.get("document_id") in ("doc-001", "stored-uuid-001")
    assert result.get("doc_type") == "sop"
    tags = result.get("tags", [])
    assert "sop" in tags
    assert "kubernetes" in tags or "k8s" in tags
    score = result.get("quality_score", 0.0)
    assert score >= 0.5, f"Expected quality >= 0.5, got {score}"


@pytest.mark.asyncio
async def test_full_pipeline_quality_branch() -> None:
    """Low-quality document should go through review path."""
    state = {
        "document_id": "doc-002",
        "raw_content": "Short.",
        "title": "Untitled",
    }

    pipeline = build_knowledge_pipeline()

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "stored-uuid-002"
    mock_repo.create_document = AsyncMock(return_value=mock_doc)
    mock_indexer = MagicMock()
    mock_indexer.index_document = AsyncMock(return_value={"indexed": True})

    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository", return_value=mock_repo),
        patch("app.search.indexer.KnowledgeIndexer", return_value=mock_indexer),
    ):
        mock_settings.return_value.llm_api_key = ""
        mock_settings.return_value.embedding_api_key = ""

        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        if hasattr(pipeline, "ainvoke"):
            result = await pipeline.ainvoke(state)
        else:
            result = pipeline(state)

    # Should end at review (status='review', need_review=True)
    assert result.get("need_review") is True
    assert result.get("status") == "review"


@pytest.mark.asyncio
async def test_full_pipeline_review_then_approve() -> None:
    """After review, approve should route to embed and complete."""
    state = {
        "document_id": "doc-003",
        "raw_content": "Too short to pass quality.",
        "title": "Untitled",
    }

    pipeline = build_knowledge_pipeline()

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "stored-uuid-003"
    mock_repo.create_document = AsyncMock(return_value=mock_doc)
    mock_indexer = MagicMock()
    mock_indexer.index_document = AsyncMock(return_value={"indexed": True})

    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository", return_value=mock_repo),
        patch("app.search.indexer.KnowledgeIndexer", return_value=mock_indexer),
    ):
        mock_settings.return_value.llm_api_key = ""
        mock_settings.return_value.embedding_api_key = ""

        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        if hasattr(pipeline, "ainvoke"):
            result = await pipeline.ainvoke(state)
        else:
            result = pipeline(state)

    assert result.get("need_review") is True
    assert result.get("status") == "review"

    # Step 2: Simulate approval — set review_decision and re-invoke
    state_approved = dict(result)
    state_approved["review_decision"] = "approved"
    state_approved["status"] = "processing"

    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.db.session.get_session_factory") as mock_factory,
        patch("app.knowledge.repository.KnowledgeRepository", return_value=mock_repo),
        patch("app.search.indexer.KnowledgeIndexer", return_value=mock_indexer),
    ):
        mock_settings.return_value.llm_api_key = ""
        mock_settings.return_value.embedding_api_key = ""

        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session

        if hasattr(pipeline, "ainvoke"):
            result2 = await pipeline.ainvoke(state_approved)
        else:
            result2 = pipeline(state_approved)

    # After approval, should complete the pipeline
    assert result2.get("stored") is True
    assert result2.get("document_id") == "stored-uuid-003"


def test_build_pipeline_type() -> None:
    """build_knowledge_pipeline should return a callable with invoke/ainvoke."""
    pipeline = build_knowledge_pipeline()
    assert hasattr(pipeline, "invoke") or hasattr(pipeline, "ainvoke") or hasattr(pipeline, "__call__")