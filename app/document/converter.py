"""
Document format converter.

Converts ParsedDocument instances into a unified Markdown representation
suitable for knowledge storage, versioning, and downstream embedding.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.document.parser import ParsedDocument


def convert_to_markdown(parsed_document: ParsedDocument) -> str:
    """Convert a ParsedDocument into unified Markdown with YAML frontmatter.

    Output format::

        ---
        title: ...
        source: ...
        format: ...
        created_at: ...
        ---

        # Title

        body content

    Args:
        parsed_document: Parsed document from DocumentParser.

    Returns:
        Markdown string with frontmatter and body.
    """
    title = parsed_document.title or "Untitled"
    source = parsed_document.source or ""
    fmt = parsed_document.format or "text"
    created_at = parsed_document.created_at
    if isinstance(created_at, datetime):
        created_at_str = created_at.isoformat()
    else:
        created_at_str = str(created_at)

    frontmatter_lines = [
        "---",
        f"title: {title}",
        f"source: {source}",
        f"format: {fmt}",
        f"created_at: {created_at_str}",
    ]

    # Include useful metadata keys in frontmatter
    meta = parsed_document.metadata or {}
    for key in ("author", "tags", "pages", "page_count", "encoding"):
        if key in meta and meta[key] not in (None, "", []):
            value = meta[key]
            if isinstance(value, list):
                frontmatter_lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
            else:
                frontmatter_lines.append(f"{key}: {value}")

    frontmatter_lines.append("---")
    frontmatter_lines.append("")

    body = (parsed_document.content or "").strip()

    # Avoid duplicating H1 if body already starts with the same title heading
    heading = f"# {title}"
    if body.startswith(heading) or body.startswith(f"# {title}\n"):
        markdown_body = body
    else:
        markdown_body = f"{heading}\n\n{body}" if body else heading

    return "\n".join(frontmatter_lines) + markdown_body + "\n"


def convert_text_to_markdown(text: str, title: Optional[str] = None) -> str:
    """Convert raw text to Markdown with an optional title heading.

    Args:
        text: Raw text content.
        title: Optional document title.

    Returns:
        Markdown formatted content.
    """
    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
        lines.append("")

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        stripped = para.strip()
        if stripped:
            lines.append(stripped)
            lines.append("")

    return "\n".join(lines)


def extract_frontmatter_dict(parsed_document: ParsedDocument) -> Dict[str, Any]:
    """Build a serializable metadata dict for indexing / storage.

    Args:
        parsed_document: Parsed document.

    Returns:
        Flat metadata dictionary.
    """
    result: Dict[str, Any] = {
        "id": parsed_document.id,
        "title": parsed_document.title,
        "format": parsed_document.format,
        "source": parsed_document.source,
        "created_at": (
            parsed_document.created_at.isoformat()
            if isinstance(parsed_document.created_at, datetime)
            else str(parsed_document.created_at)
        ),
    }
    result.update(parsed_document.metadata or {})
    return result
