"""
Document parsing and conversion package.

Handles ingestion of enterprise knowledge document formats:
- PDF text / table extraction (PyMuPDF)
- Word document parsing with heading hierarchy (python-docx)
- Markdown parsing with YAML frontmatter (python-frontmatter)
- Plain text with UTF-8 / GBK auto-detection
- Unified Markdown conversion for knowledge storage
"""

from app.document.converter import convert_text_to_markdown, convert_to_markdown
from app.document.importer import DocumentImporter, document_importer
from app.document.parser import (
    DocumentParseError,
    DocumentParser,
    ParsedDocument,
    UnsupportedFormatError,
    parse_docx,
    parse_file,
    parse_markdown,
    parse_pdf,
    parse_txt,
)

__all__ = [
    "DocumentImporter",
    "DocumentParseError",
    "DocumentParser",
    "ParsedDocument",
    "UnsupportedFormatError",
    "convert_text_to_markdown",
    "convert_to_markdown",
    "document_importer",
    "parse_docx",
    "parse_file",
    "parse_markdown",
    "parse_pdf",
    "parse_txt",
]
