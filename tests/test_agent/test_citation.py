"""Tests for citation extraction and models.

Tests CitationSource model and CitationExtractor functionality.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import pytest

from app.citation.extractor import CitationExtractor, extract_citations
from app.citation.models import Citation, CitationSource


@dataclass
class MockResult:
    """Mock search result for testing."""
    id: str = ""
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestCitationSource:
    """Tests for CitationSource model."""

    def test_citation_source_fields(self) -> None:
        """CitationSource should store all fields."""
        source = CitationSource(
            document_id="doc-1",
            title="Nginx故障处理SOP",
            content_snippet="502通常表示上游服务异常",
            source="knowledge_base",
            page=5,
            score=0.93,
        )
        assert source.document_id == "doc-1"
        assert source.title == "Nginx故障处理SOP"
        assert source.content_snippet == "502通常表示上游服务异常"
        assert source.source == "knowledge_base"
        assert source.page == 5
        assert source.score == 0.93

    def test_to_dict(self) -> None:
        """to_dict should return serializable dict."""
        source = CitationSource(
            document_id="doc-1",
            title="测试文档",
            content_snippet="测试内容",
            score=0.95,
        )
        d = source.to_dict()
        assert d["document_id"] == "doc-1"
        assert d["title"] == "测试文档"
        assert d["content_snippet"] == "测试内容"
        assert d["score"] == 0.95


class TestCitation:
    """Tests for Citation model."""

    def test_citation_fields(self) -> None:
        """Citation should hold sources list, answer, and confidence."""
        sources = [
            CitationSource(document_id="1", title="SOP", content_snippet="内容", score=0.9),
        ]
        citation = Citation(sources=sources, answer="测试答案", confidence=0.85)
        assert len(citation.sources) == 1
        assert citation.answer == "测试答案"
        assert citation.confidence == 0.85

    def test_to_dict(self) -> None:
        """Citation to_dict should include all nested fields."""
        sources = [
            CitationSource(document_id="1", title="SOP", content_snippet="内容", score=0.9),
        ]
        citation = Citation(sources=sources, answer="答案", confidence=0.8)
        d = citation.to_dict()
        assert d["answer"] == "答案"
        assert len(d["sources"]) == 1
        assert d["sources"][0]["document_id"] == "1"


class TestCitationExtractor:
    """Tests for CitationExtractor."""

    def test_extract_empty_results(self) -> None:
        """Empty results should produce empty citations."""
        extractor = CitationExtractor()
        sources = extractor.extract([])
        assert sources == []

    def test_extract_sorted_by_score(self) -> None:
        """Citations should be sorted by score descending."""
        results = [
            MockResult(id="3", title="文档C", snippet="内容C", score=0.3),
            MockResult(id="1", title="文档A", snippet="内容A", score=0.9),
            MockResult(id="2", title="文档B", snippet="内容B", score=0.6),
        ]
        extractor = CitationExtractor()
        sources = extractor.extract(results)
        assert sources[0].title == "文档A"
        assert sources[1].title == "文档B"
        assert sources[2].title == "文档C"

    def test_extract_max_sources(self) -> None:
        """Should respect max_sources limit."""
        results = [
            MockResult(id=str(i), title=f"文档{i}", snippet=f"内容{i}", score=1.0)
            for i in range(20)
        ]
        extractor = CitationExtractor()
        sources = extractor.extract(results, max_sources=3)
        assert len(sources) == 3

    def test_extract_deduplication(self) -> None:
        """Duplicate titles should be deduplicated."""
        results = [
            MockResult(id="1", title="相同文档", snippet="A", score=0.9),
            MockResult(id="2", title="相同文档", snippet="B", score=0.5),
        ]
        extractor = CitationExtractor()
        sources = extractor.extract(results)
        assert len(sources) == 1

    def test_snippet_truncation(self) -> None:
        """Content snippet should be truncated to 200 chars."""
        long_content = "A" * 500
        results = [
            MockResult(id="1", title="文档", snippet=long_content, score=1.0),
        ]
        extractor = CitationExtractor()
        sources = extractor.extract(results)
        assert len(sources[0].content_snippet) <= 200


class TestExtractCitations:
    """Tests for extract_citations convenience function."""

    def test_extract_citations_basic(self) -> None:
        """extract_citations should return CitationSource list."""
        results = [
            MockResult(id="1", title="文档A", snippet="内容A", score=0.9),
        ]
        sources = extract_citations(results)
        assert len(sources) == 1
        assert sources[0].title == "文档A"