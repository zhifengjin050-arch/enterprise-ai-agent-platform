"""Tests for Markdown converter and importer integration."""

from __future__ import annotations

from pathlib import Path

from app.document.converter import convert_to_markdown
from app.document.importer import DocumentImporter
from app.document.parser import ParsedDocument, parse_markdown


def test_convert_to_markdown_format(markdown_file: Path) -> None:
    """Converter should emit YAML frontmatter and title heading."""
    parsed = parse_markdown(markdown_file)
    md = convert_to_markdown(parsed)

    assert md.startswith("---\n")
    assert "title: Kubernetes部署规范" in md
    assert "source:" in md
    assert "format: markdown" in md
    assert "created_at:" in md
    assert "---\n\n# Kubernetes部署规范" in md or "# Kubernetes部署规范" in md


def test_convert_parsed_document_direct() -> None:
    """Converter works with a manually constructed ParsedDocument."""
    parsed = ParsedDocument(
        title="Test Doc",
        content="Hello world",
        format="text",
        metadata={"author": "QA"},
        source="/tmp/test.txt",
    )
    md = convert_to_markdown(parsed)
    assert "title: Test Doc" in md
    assert "format: text" in md
    assert "author: QA" in md
    assert "# Test Doc" in md
    assert "Hello world" in md


async def test_importer_submits_to_workflow(markdown_file: Path) -> None:
    """DocumentImporter should parse, convert, and call workflow."""
    importer = DocumentImporter()
    result = await importer.import_document(markdown_file)

    assert "parsed" in result
    assert "markdown" in result
    assert result["parsed"]["title"] == "Kubernetes部署规范"
    assert result["markdown"].startswith("---")
    assert result["workflow_result"] is not None
    # workflow may return deferred or full pipeline state
    wf = result["workflow_result"]
    assert "document_id" in wf or "status" in wf or "parsed_document" in wf
