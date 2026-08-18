"""Tests for HybridSearch with RRF fusion."""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock

import pytest

from app.search.hybrid import HybridResult, HybridSearch, rrf_score
from app.search.fulltext import DocumentResult
from app.search.semantic import SemanticResult


class TestRRFScore:
    """Verify RRF score calculation."""

    def test_rrf_score_rank_1(self) -> None:
        assert rrf_score(1, k=60) == pytest.approx(1 / 61)

    def test_rrf_score_rank_10(self) -> None:
        assert rrf_score(10, k=60) == pytest.approx(1 / 70)

    def test_rrf_score_custom_k(self) -> None:
        assert rrf_score(5, k=30) == pytest.approx(1 / 35)


@pytest.mark.asyncio
async def test_hybrid_search_combines_results() -> None:
    """Verify RRF correctly merges fulltext and semantic results."""
    mock_fts = AsyncMock()
    mock_fts.search.return_value = [
        DocumentResult(id="doc-1", title="Doc A", snippet="...", score=1.0, doc_type="sop"),
        DocumentResult(id="doc-2", title="Doc B", snippet="...", score=0.8, doc_type="general"),
        DocumentResult(id="doc-3", title="Doc C", snippet="...", score=0.6, doc_type="incident"),
    ]

    mock_sem = AsyncMock()
    mock_sem.search.return_value = [
        SemanticResult(id="doc-4", title="Doc D", content="...", score=0.95, metadata={}),
        SemanticResult(id="doc-2", title="Doc B", content="...", score=0.90, metadata={}),
        SemanticResult(id="doc-1", title="Doc A", content="...", score=0.85, metadata={}),
    ]

    engine = HybridSearch(
        fulltext=mock_fts,  # type: ignore[arg-type]
        semantic=mock_sem,  # type: ignore[arg-type]
        rrf_k=60,
    )

    results: List[HybridResult] = await engine.search(query="test", top_k=5)

    # doc-1 appears in both (rank 1 in FTS, rank 3 in semantic)
    # doc-2 appears in both (rank 2 in FTS, rank 2 in semantic)
    # doc-3 only in FTS (rank 3)
    # doc-4 only in semantic (rank 1)
    assert len(results) == 4
    assert results[0].id in ("doc-1", "doc-2", "doc-4")  # top should have contributions from both
    # Verify RRF: doc-1 = 1/61 + 1/63, doc-2 = 1/62 + 1/62, doc-4 = 1/61
    scores = {r.id: r.score for r in results}
    assert scores["doc-1"] == pytest.approx(1 / 61 + 1 / 63)
    assert scores["doc-2"] == pytest.approx(2 / 62)
    assert scores["doc-4"] == pytest.approx(1 / 61)
    assert scores["doc-3"] == pytest.approx(1 / 63)