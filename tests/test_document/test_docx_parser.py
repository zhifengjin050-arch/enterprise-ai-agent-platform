"""Tests for Word (docx) document parsing."""

from __future__ import annotations

from pathlib import Path

from app.document.parser import ParsedDocument, parse_docx


def test_docx_heading_conversion(docx_file: Path) -> None:
    """Word headings should become Markdown heading markers."""
    result = parse_docx(docx_file)
    assert isinstance(result, ParsedDocument)
    assert result.format == "docx"
    assert "# Kubernetes故障排查" in result.content
    assert "## Pod OOM" in result.content
    assert "内存不足" in result.content


def test_docx_table_conversion(docx_file: Path) -> None:
    """Word tables should be converted to Markdown tables."""
    result = parse_docx(docx_file)
    assert "|Name|Value|" in result.content.replace(" ", "")
    assert result.metadata["tables"] >= 1
    assert result.metadata["paragraph_count"] >= 1
    assert result.metadata["author"] == "SRE Team"
