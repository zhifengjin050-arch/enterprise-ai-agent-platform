"""Tests for PDF document parsing."""

from __future__ import annotations

from pathlib import Path

from app.document.parser import ParsedDocument, parse_pdf


def test_pdf_text_extraction(pdf_file: Path) -> None:
    """PDF text content should be extracted."""
    result = parse_pdf(pdf_file)
    assert isinstance(result, ParsedDocument)
    assert result.format == "pdf"
    assert "Enterprise Knowledge Sample PDF" in result.content
    assert "Page 1 content" in result.content


def test_pdf_metadata(pdf_file: Path) -> None:
    """PDF metadata should include pages, author, creator."""
    result = parse_pdf(pdf_file)
    assert result.metadata["pages"] == 2
    assert result.metadata["page_count"] == 2
    assert result.metadata["author"] == "Knowledge Copilot"
    assert result.metadata["creator"] == "PyMuPDF Test"
    assert "images" in result.metadata
    assert result.title == "Sample PDF Doc"
    assert result.source == str(pdf_file)


def test_pdf_page_structure(pdf_file: Path) -> None:
    """PDF content should preserve page markers."""
    result = parse_pdf(pdf_file)
    assert "<!-- page:1 -->" in result.content
    assert "<!-- page:2 -->" in result.content
