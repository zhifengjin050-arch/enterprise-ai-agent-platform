"""Tests for TXT document parsing with encoding fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.document.parser import (
    DocumentParser,
    ParsedDocument,
    UnsupportedFormatError,
    parse_txt,
)


def test_txt_utf8(txt_utf8_file: Path) -> None:
    """UTF-8 text files should be decoded correctly."""
    result = parse_txt(txt_utf8_file)
    assert isinstance(result, ParsedDocument)
    assert result.format == "text"
    assert "Pod OOM" in result.content
    assert result.metadata["encoding"] == "utf-8"


def test_txt_gbk(txt_gbk_file: Path) -> None:
    """GBK text files should fall back successfully."""
    result = parse_txt(txt_gbk_file)
    assert isinstance(result, ParsedDocument)
    assert "服务器重启流程" in result.content
    assert result.metadata["encoding"] == "gbk"


def test_document_parser_unsupported(tmp_path: Path) -> None:
    """Unsupported extensions should raise UnsupportedFormatError."""
    bad = tmp_path / "file.xlsx"
    bad.write_text("x", encoding="utf-8")
    parser = DocumentParser()
    with pytest.raises(UnsupportedFormatError):
        parser.parse(bad)
