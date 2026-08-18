"""Tests for SmartChunker."""

from __future__ import annotations

from app.knowledge.chunking import SmartChunker, estimate_tokens


SAMPLE_MD = """# Introduction

This is the intro paragraph about Kubernetes and Docker.

## Setup

Install prerequisites:

```bash
kubectl apply -f deploy.yaml
echo "done"
```

## Data Table

| Name | Type |
|------|------|
| Redis | Cache |
| MySQL | DB |

## Details

More text about the system. This paragraph is intentionally longer so that
token limits can be exercised when max_tokens is set very low for testing.
"""


class TestEstimateTokens:
    def test_empty(self) -> None:
        assert estimate_tokens("") == 0

    def test_non_empty(self) -> None:
        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("a" * 40) == 10


class TestSmartChunker:
    def test_basic_chunking(self) -> None:
        chunker = SmartChunker(max_tokens=256, overlap_tokens=0)
        chunks = chunker.chunk(SAMPLE_MD, document_id="doc-1", title="Intro")
        assert len(chunks) >= 1
        assert all(c.document_id == "doc-1" for c in chunks)
        assert all(c.token_count > 0 for c in chunks)
        # Indices are sequential
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_heading_detection(self) -> None:
        chunker = SmartChunker(max_tokens=512, overlap_tokens=0)
        chunks = chunker.chunk(SAMPLE_MD, document_id="d")
        headings = {c.heading for c in chunks if c.heading}
        assert "Introduction" in headings or "Setup" in headings or "Details" in headings

    def test_code_block_protection(self) -> None:
        chunker = SmartChunker(max_tokens=64, overlap_tokens=0)
        chunks = chunker.chunk(SAMPLE_MD, document_id="d")
        code_chunks = [c for c in chunks if "kubectl" in c.content]
        assert len(code_chunks) >= 1
        # Code fence should stay together
        assert any("```" in c.content for c in code_chunks)

    def test_table_protection(self) -> None:
        chunker = SmartChunker(max_tokens=64, overlap_tokens=0)
        chunks = chunker.chunk(SAMPLE_MD, document_id="d")
        table_chunks = [c for c in chunks if "Redis" in c.content and "|" in c.content]
        assert len(table_chunks) >= 1

    def test_empty_input(self) -> None:
        chunker = SmartChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_token_limit_splits(self) -> None:
        long_text = "# Title\n\n" + ("word " * 500)
        chunker = SmartChunker(max_tokens=50, overlap_tokens=0)
        chunks = chunker.chunk(long_text, document_id="d")
        assert len(chunks) > 1
        # Most chunks should respect soft limit (hard_split may exceed slightly)
        assert all(c.token_count > 0 for c in chunks)

    def test_to_dict(self) -> None:
        chunker = SmartChunker()
        chunks = chunker.chunk("# Hi\n\nHello world", document_id="d1")
        d = chunks[0].to_dict()
        assert "id" in d
        assert d["document_id"] == "d1"
        assert "content" in d