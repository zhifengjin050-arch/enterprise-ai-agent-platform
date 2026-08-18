"""Tests for FullTextSearch engine."""

from __future__ import annotations

from typing import List

import pytest

from app.search.fulltext import DocumentResult, FullTextSearch


class TestMakeSnippet:
    """Verify snippet extraction logic."""

    def test_snippet_contains_query(self) -> None:
        fts = FullTextSearch()
        content = "This is a long document about Kubernetes deployment best practices."
        snippet = fts._make_snippet(content, "Kubernetes")
        assert "Kubernetes" in snippet

    def test_snippet_no_match(self) -> None:
        fts = FullTextSearch()
        content = "Some random text here."
        snippet = fts._make_snippet(content, "missing")
        assert snippet == content[:150]

    def test_snippet_empty_content(self) -> None:
        fts = FullTextSearch()
        assert fts._make_snippet("", "query") == ""

    def test_snippet_long_content(self) -> None:
        fts = FullTextSearch()
        content = "A" * 1000 + "Kubernetes" + "B" * 1000
        snippet = fts._make_snippet(content, "Kubernetes")
        assert "Kubernetes" in snippet
        assert len(snippet) <= 310  # 150 + len("Kubernetes") + 150 + "..." padding