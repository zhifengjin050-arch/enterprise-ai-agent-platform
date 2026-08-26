"""Tests for Reranker."""

from __future__ import annotations

from dataclasses import dataclass

from app.knowledge.reranker import Reranker, _lexical_overlap


@dataclass
class FakeResult:
    content: str
    score: float
    title: str = ""


class TestReranker:
    def test_lexical_overlap(self) -> None:
        assert _lexical_overlap("kubernetes docker", "kubernetes and docker setup") > 0
        assert _lexical_overlap("abc", "xyz") == 0.0

    def test_rerank_orders_by_relevance(self) -> None:
        reranker = Reranker(lexical_weight=0.8, original_weight=0.2)
        results = [
            FakeResult(content="unrelated text about cooking", score=0.9),
            FakeResult(content="kubernetes cluster deployment guide", score=0.5),
            FakeResult(content="docker container basics", score=0.4),
        ]
        top = reranker.rerank("kubernetes docker", results, top_n=2)
        assert len(top) == 2
        # The kubernetes-related doc should rank above cooking
        assert "kubernetes" in top[0].content.lower() or "docker" in top[0].content.lower()

    def test_rerank_empty(self) -> None:
        assert Reranker().rerank("q", [], top_n=5) == []

    def test_rerank_top_n(self) -> None:
        results = [FakeResult(content=f"doc {i} kubernetes", score=0.1 * i) for i in range(10)]
        top = Reranker().rerank("kubernetes", results, top_n=3)
        assert len(top) == 3

    def test_custom_score_fn(self) -> None:
        def always_one(q: str, t: str) -> float:
            return 1.0 if "prefer" in t else 0.0

        reranker = Reranker(score_fn=always_one)
        results = [
            FakeResult(content="ignore me", score=0.9),
            FakeResult(content="prefer this", score=0.1),
        ]
        top = reranker.rerank("q", results, top_n=1)
        assert top[0].content == "prefer this"
