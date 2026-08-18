"""Tests for Markdown document parsing with frontmatter."""

from __future__ import annotations

from pathlib import Path

from app.document.parser import ParsedDocument, parse_markdown


def test_markdown_frontmatter(markdown_file: Path) -> None:
    """YAML frontmatter should be extracted into metadata."""
    result = parse_markdown(markdown_file)
    assert isinstance(result, ParsedDocument)
    assert result.format == "markdown"
    assert result.title == "Kubernetes部署规范"
    assert result.metadata["title"] == "Kubernetes部署规范"
    assert result.metadata["author"] == "SRE团队"
    assert "k8s" in result.metadata["tags"]
    assert "docker" in result.metadata["tags"]


def test_markdown_body(markdown_file: Path) -> None:
    """Frontmatter should not appear in content body."""
    result = parse_markdown(markdown_file)
    assert "title: Kubernetes部署规范" not in result.content
    assert "Kubernetes 集群部署标准" in result.content
    assert result.content.startswith("#") or "部署" in result.content
