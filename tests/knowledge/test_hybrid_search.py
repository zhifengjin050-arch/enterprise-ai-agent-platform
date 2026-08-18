"""Tests for hybrid search and KnowledgeRetriever."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge.hybrid_search import IntelligenceHybridSearch, IntelligenceHybridResult
from app.knowledge.retrieval import KnowledgeRetriever, RetrievalResult
from app.search.hybrid import HybridResult


class FakeHybrid:
    async def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[HybridResult]:
        return [
            HybridResult(
                id="doc-1",
                title="K8s Guide",
                snippet="Kubernetes deployment guide",
                score=0.8,
                metadata={},
            ),
            HybridResult(
                id="doc-2",
                title="Cooking",
                snippet="How to cook pasta",
                score=0.3,
                metadata={},
            ),
        ]


class TestIntelligenceHybridSearch:
    async def test_search_maps_results(self) -> None:
        search = IntelligenceHybridSearch(hybrid=FakeHybrid())  # type: ignore[arg-type]
        results = await search.search("kubernetes", top_k=10, use_graph=False)
        assert len(results) == 2
        assert results[0].document_id == "doc-1"
        assert results[0].source == "hybrid"
        assert results[0].score >= results[1].score

    async def test_to_dict(self) -> None:
        r = IntelligenceHybridResult(
            document_id="d1", chunk_id="c1", score=0.5, title="T", content="C"
        )
        d = r.to_dict()
        assert d["document_id"] == "d1"
        assert d["chunk_id"] == "c1"


class TestKnowledgeRetriever:
    async def test_retrieve_with_rerank(self) -> None:
        hybrid = IntelligenceHybridSearch(hybrid=FakeHybrid())  # type: ignore[arg-type]
        retriever = KnowledgeRetriever(hybrid=hybrid, recall_k=10, top_n=1)
        results = await retriever.retrieve(
            "kubernetes",
            use_graph=False,
            use_rerank=True,
        )
        assert len(results) == 1
        assert isinstance(results[0], RetrievalResult)
        assert results[0].document_id in ("doc-1", "doc-2")

    async def test_retrieve_without_rerank(self) -> None:
        hybrid = IntelligenceHybridSearch(hybrid=FakeHybrid())  # type: ignore[arg-type]
        retriever = KnowledgeRetriever(hybrid=hybrid, recall_k=10, top_n=2)
        results = await retriever.retrieve(
            "kubernetes",
            use_graph=False,
            use_rerank=False,
        )
        assert len(results) == 2

    def test_retrieval_result_to_dict(self) -> None:
        r = RetrievalResult(
            document_id="d",
            chunk_id="c",
            score=0.9,
            source="hybrid",
            content="text",
            title="T",
        )
        d = r.to_dict()
        assert d["document_id"] == "d"
        assert d["score"] == 0.9
        assert set(d.keys()) >= {
            "document_id",
            "chunk_id",
            "score",
            "source",
            "metadata",
        }