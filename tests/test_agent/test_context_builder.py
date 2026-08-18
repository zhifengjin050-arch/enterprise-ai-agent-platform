"""Tests for context builder.

Tests deduplication, token limiting, and text formatting
from hybrid search results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import pytest

from app.query.builder import ContextBuilder, ContextDocument, build_llm_context


@dataclass
class MockResult:
    """Mock search result for testing."""
    id: str = ""
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestContextBuilder:
    """Tests for ContextBuilder."""

    def test_empty_results(self) -> None:
        """Empty results should produce empty context."""
        builder = ContextBuilder()
        context = builder.build([])
        assert context == []

    def test_deduplication(self) -> None:
        """Duplicate titles should be deduplicated (keep highest score)."""
        results = [
            MockResult(id="1", title="Nginx故障处理SOP", snippet="内容A", score=0.8),
            MockResult(id="2", title="Nginx故障处理SOP", snippet="内容B", score=0.5),
            MockResult(id="3", title="Kubernetes部署指南", snippet="内容C", score=0.9),
        ]
        builder = ContextBuilder(max_tokens=12000)
        context = builder.build(results)
        assert len(context) == 2  # dedup
        assert context[0].title == "Kubernetes部署指南"  # highest score first

    def test_token_limit(self) -> None:
        """Context should be limited by max_tokens."""
        results = [
            MockResult(id=str(i), title=f"文档{i}", snippet="A" * 500, score=1.0)
            for i in range(100)
        ]
        builder = ContextBuilder(max_tokens=500)
        context = builder.build(results)
        # Token limit ensures only a subset fits
        assert len(context) < len(results)

    def test_sorted_by_score(self) -> None:
        """Results should be sorted by score descending."""
        results = [
            MockResult(id="1", title="Low", snippet="", score=0.3),
            MockResult(id="2", title="High", snippet="", score=0.9),
            MockResult(id="3", title="Medium", snippet="", score=0.6),
        ]
        builder = ContextBuilder()
        context = builder.build(results)
        assert context[0].title == "High"
        assert context[1].title == "Medium"
        assert context[2].title == "Low"

    def test_context_document_fields(self) -> None:
        """ContextDocument should hold correct fields."""
        doc = ContextDocument(
            title="测试文档",
            content="测试内容",
            source="知识库",
            score=0.95,
        )
        assert doc.title == "测试文档"
        assert doc.content == "测试内容"
        assert doc.source == "知识库"
        assert doc.score == 0.95

    def test_to_text_formatting(self) -> None:
        """to_text should produce formatted markdown-style text."""
        builder = ContextBuilder()
        context = [
            ContextDocument(title="文档A", content="内容A", source="知识库", score=0.9),
        ]
        text = builder.to_text(context)
        assert "[文档 1]" in text
        assert "文档A" in text
        assert "内容A" in text


class TestBuildLLMContext:
    """Tests for build_llm_context convenience function."""

    def test_build_llm_context_basic(self) -> None:
        """build_llm_context should return formatted string."""
        results = [
            MockResult(id="1", title="文档A", snippet="内容A", score=0.9),
            MockResult(id="2", title="文档B", snippet="内容B", score=0.8),
        ]
        text = build_llm_context(results)
        assert "[文档 1]" in text
        assert "文档A" in text
        assert "文档B" in text

    def test_build_llm_context_empty(self) -> None:
        """build_llm_context with empty results should return empty."""
        text = build_llm_context([])
        assert text == ""