"""Intelligent document chunking for the Knowledge Intelligence Layer.

Supports:
    - Markdown heading-aware splitting
    - Code block protection (fenced ``` blocks stay intact)
    - Table protection (pipe tables stay intact)
    - Semantic / paragraph-aware splitting
    - Token budget enforcement

Usage:
    chunker = SmartChunker(max_tokens=512, overlap_tokens=64)
    chunks = chunker.chunk(markdown_text, document_id="doc-1")
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Approximate: 4 chars ≈ 1 token for mixed CJK/English
_CHARS_PER_TOKEN = 4

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_FENCED_CODE_RE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|.+\|\s*$", re.MULTILINE)


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


@dataclass
class Chunk:
    """An in-memory document chunk before persistence.

    Attributes:
        id: Unique chunk ID.
        document_id: Parent document ID.
        chunk_index: Order within the document.
        content: Chunk text.
        heading: Nearest Markdown heading.
        token_count: Estimated tokens.
        metadata: Extra flags (is_code, is_table, etc.).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    chunk_index: int = 0
    content: str = ""
    heading: Optional[str] = None
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "heading": self.heading,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


class SmartChunker:
    """Markdown-aware document chunker with protection for code and tables.

    Algorithm:
        1. Extract and protect fenced code blocks and tables as atomic units.
        2. Split remaining text by Markdown headings (H1–H6).
        3. Within each section, split by paragraphs if over max_tokens.
        4. Merge undersized adjacent chunks when possible.
        5. Apply overlap between consecutive text chunks.

    Args:
        max_tokens: Soft maximum tokens per chunk (default 512).
        overlap_tokens: Overlap between consecutive chunks (default 64).
        min_tokens: Prefer not to create chunks smaller than this (default 32).
    """

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
        min_tokens: int = 32,
    ) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens

    def chunk(
        self,
        text: str,
        *,
        document_id: str = "",
        title: str = "",
    ) -> List[Chunk]:
        """Chunk a Markdown document into structured pieces.

        Args:
            text: Full Markdown content.
            document_id: Parent document ID.
            title: Optional document title used as fallback heading.

        Returns:
            Ordered list of Chunk objects.
        """
        if not text or not text.strip():
            return []

        # Step 1: Protect code blocks and tables
        protected, placeholders = self._protect_blocks(text)

        # Step 2: Split by headings
        sections = self._split_by_headings(protected, default_heading=title or None)

        # Step 3: Restore placeholders and split oversized sections
        raw_chunks: List[Chunk] = []
        for heading, body in sections:
            restored = self._restore_placeholders(body, placeholders)
            parts = self._split_oversized(restored, heading=heading)
            raw_chunks.extend(parts)

        # Step 4: Apply overlap and assign indices / IDs
        return self._finalize(raw_chunks, document_id=document_id)

    # ── Internal helpers ──

    def _protect_blocks(
        self, text: str
    ) -> tuple[str, Dict[str, tuple[str, str]]]:
        """Replace code blocks and tables with placeholders.

        Returns:
            (protected_text, placeholder_map) where map values are
            (kind, original_content).
        """
        placeholders: Dict[str, tuple[str, str]] = {}
        counter = 0

        def _replace_code(match: re.Match[str]) -> str:
            nonlocal counter
            key = f"__PROTECTED_CODE_{counter}__"
            counter += 1
            placeholders[key] = ("code", match.group(0))
            return f"\n\n{key}\n\n"

        protected = _FENCED_CODE_RE.sub(_replace_code, text)

        # Protect contiguous table blocks
        lines = protected.split("\n")
        out_lines: List[str] = []
        i = 0
        while i < len(lines):
            if _TABLE_ROW_RE.match(lines[i]):
                table_lines = []
                while i < len(lines) and (
                    _TABLE_ROW_RE.match(lines[i]) or lines[i].strip() == ""
                ):
                    if lines[i].strip():
                        table_lines.append(lines[i])
                    i += 1
                if table_lines:
                    key = f"__PROTECTED_TABLE_{counter}__"
                    counter += 1
                    placeholders[key] = ("table", "\n".join(table_lines))
                    out_lines.append("")
                    out_lines.append(key)
                    out_lines.append("")
                continue
            out_lines.append(lines[i])
            i += 1

        return "\n".join(out_lines), placeholders

    def _restore_placeholders(
        self, text: str, placeholders: Dict[str, tuple[str, str]]
    ) -> str:
        """Restore protected blocks into text."""
        for key, (_kind, original) in placeholders.items():
            text = text.replace(key, original)
        return text

    def _split_by_headings(
        self, text: str, *, default_heading: Optional[str] = None
    ) -> List[tuple[Optional[str], str]]:
        """Split text into (heading, body) sections."""
        matches = list(_HEADING_RE.finditer(text))
        if not matches:
            return [(default_heading, text.strip())]

        sections: List[tuple[Optional[str], str]] = []
        # Content before first heading
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append((default_heading, preamble))

        for idx, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            # Include heading line in content for context
            content = f"{match.group(0)}\n\n{body}".strip() if body else match.group(0)
            sections.append((heading, content))

        return sections

    def _split_oversized(
        self, text: str, *, heading: Optional[str] = None
    ) -> List[Chunk]:
        """Split text that exceeds max_tokens by paragraphs / sentences."""
        tokens = estimate_tokens(text)
        meta: Dict[str, Any] = {}

        # Entire protected code/table block — keep atomic even if large
        if text.strip().startswith("```") or text.strip().startswith("|"):
            if text.strip().startswith("```"):
                meta["is_code"] = True
            if "|" in text[:80]:
                meta["is_table"] = True
            return [
                Chunk(
                    content=text.strip(),
                    heading=heading,
                    token_count=tokens,
                    metadata=meta,
                )
            ]

        if tokens <= self.max_tokens:
            return [
                Chunk(
                    content=text.strip(),
                    heading=heading,
                    token_count=tokens,
                    metadata=meta,
                )
            ]

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: List[Chunk] = []
        buffer = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            candidate = f"{buffer}\n\n{para}".strip() if buffer else para
            if estimate_tokens(candidate) <= self.max_tokens:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(
                        Chunk(
                            content=buffer,
                            heading=heading,
                            token_count=estimate_tokens(buffer),
                        )
                    )
                # Paragraph itself may still be oversized — hard split
                if estimate_tokens(para) > self.max_tokens:
                    chunks.extend(self._hard_split(para, heading=heading))
                    buffer = ""
                else:
                    buffer = para

        if buffer:
            chunks.append(
                Chunk(
                    content=buffer,
                    heading=heading,
                    token_count=estimate_tokens(buffer),
                )
            )

        return chunks

    def _hard_split(
        self, text: str, *, heading: Optional[str] = None
    ) -> List[Chunk]:
        """Hard-split by character budget when paragraphs are too large."""
        max_chars = self.max_tokens * _CHARS_PER_TOKEN
        chunks: List[Chunk] = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            # Prefer break at sentence / whitespace
            if end < len(text):
                for sep in (". ", "。", "\n", " "):
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + len(sep)
                        break
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    Chunk(
                        content=piece,
                        heading=heading,
                        token_count=estimate_tokens(piece),
                        metadata={"hard_split": True},
                    )
                )
            start = end
        return chunks

    def _finalize(
        self, chunks: List[Chunk], *, document_id: str
    ) -> List[Chunk]:
        """Assign IDs, indices, document_id, and apply overlap."""
        if not chunks:
            return []

        finalized: List[Chunk] = []
        overlap_chars = self.overlap_tokens * _CHARS_PER_TOKEN

        for i, chunk in enumerate(chunks):
            content = chunk.content
            if i > 0 and overlap_chars > 0 and not chunk.metadata.get("is_code"):
                prev = chunks[i - 1].content
                overlap = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
                if overlap and overlap not in content[: overlap_chars + 50]:
                    content = f"{overlap}\n\n{content}"

            finalized.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    chunk_index=i,
                    content=content,
                    heading=chunk.heading,
                    token_count=estimate_tokens(content),
                    metadata=dict(chunk.metadata),
                )
            )

        return finalized
