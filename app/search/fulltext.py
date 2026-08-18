"""Full-text search engine.

Provides keyword-based search over knowledge documents using
SQLite FTS5 (development) or PostgreSQL full-text search (production).

Design:
  - Dev environment: creates a virtual FTS5 table over knowledge_documents
  - Prod environment: uses PostgreSQL to_tsvector / tsquery
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.knowledge.models import DocumentStatus, KnowledgeDocument


@dataclass
class DocumentResult:
    """A single full-text search result."""

    id: str
    title: str
    snippet: str
    score: float
    doc_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# FTS5 virtual table DDL (created lazily if using SQLite)
_FTS5_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    title, content, doc_type,
    content=knowledge_documents,
    content_rowid=id,
    tokenize='porter unicode61'
)
"""
_FTS5_REFRESH = """
INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')
"""


class FullTextSearch:
    """Full-text search engine backed by SQLite FTS5 or PostgreSQL FTS.

    Automatically detects the database backend and selects the
    appropriate strategy.
    """

    def __init__(self) -> None:
        self._fts_initialized: bool = False

    async def _ensure_fts(self, session: AsyncSession) -> None:
        """Create/rebuild the FTS5 virtual table on SQLite.

        No-op on PostgreSQL (uses native tsvector columns).
        """
        if self._fts_initialized:
            return
        # Check if using SQLite
        dialect = session.bind.dialect.name if session.bind else "sqlite"
        if dialect == "sqlite":
            try:
                await session.execute(text(_FTS5_CREATE))
                await session.execute(text(_FTS5_REFRESH))
                await session.commit()
            except Exception as exc:
                logger.warning("FTS5 initialization failed, falling back to LIKE: %s", exc)
        self._fts_initialized = True

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DocumentResult]:
        """Execute a full-text search against the knowledge base.

        Args:
            query: Search query string.
            filters: Optional filters (doc_type, status, etc.).
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            List of DocumentResult ordered by relevance.
        """
        factory = get_session_factory()
        async with factory() as session:
            await self._ensure_fts(session)
            dialect = session.bind.dialect.name if session.bind else "sqlite"

            if dialect == "sqlite":
                return await self._search_fts5(session, query, filters, limit, offset)
            else:
                return await self._search_pg(session, query, filters, limit, offset)

    async def _search_fts5(
        self,
        session: AsyncSession,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        offset: int,
    ) -> List[DocumentResult]:
        """Search using SQLite FTS5."""
        # Sanitize query for FTS5 syntax
        safe_query = " ".join(
            re.sub(r'[^\w\u4e00-\u9fff]', ' ', query).split()
        )
        if not safe_query.strip():
            return []

        fts_query = "\"" + safe_query + "\"" if " " in safe_query else safe_query

        sql = text("""
            SELECT
                d.id, d.title, d.content, d.doc_type, d.status,
                rank AS score
            FROM knowledge_fts
            JOIN knowledge_documents d ON knowledge_fts.rowid = d.id
            WHERE knowledge_fts MATCH :query
              AND d.status = :active_status
            ORDER BY rank
            LIMIT :lim OFFSET :off
        """)

        bind_params: Dict[str, Any] = {
            "query": fts_query,
            "active_status": "active",
            "lim": limit,
            "off": offset,
        }

        # Apply additional filters
        where_clause = ""
        if filters:
            if filters.get("doc_type"):
                where_clause += " AND d.doc_type = :doc_type"
                bind_params["doc_type"] = filters["doc_type"]

        if where_clause:
            sql = text(sql.text + where_clause)  # type: ignore[assignment]

        try:
            result = await session.execute(sql, bind_params)
        except Exception as exc:
            logger.warning("FTS5 query failed, falling back to LIKE: %s", exc)
            return await self._search_like(session, query, filters, limit, offset)

        rows = result.fetchall()
        return [
            DocumentResult(
                id=str(row[0]),
                title=row[1] or "",
                snippet=self._make_snippet(row[2] or "", query),
                score=float(row[5]) if row[5] is not None else 0.0,
                doc_type=str(row[3] or ""),
                metadata={
                    "id": str(row[0]),
                    "title": row[1] or "",
                    "doc_type": str(row[3] or ""),
                    "status": str(row[4] or ""),
                },
            )
            for row in rows
        ]

    async def _search_pg(
        self,
        session: AsyncSession,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        offset: int,
    ) -> List[DocumentResult]:
        """Search using PostgreSQL to_tsvector."""
        stmt = (
            select(
                KnowledgeDocument.id,
                KnowledgeDocument.title,
                KnowledgeDocument.content,
                KnowledgeDocument.doc_type,
                KnowledgeDocument.status,
                text(
                    "ts_rank(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,'')), plainto_tsquery('simple', :q)) AS score"
                ),
            )
            .where(KnowledgeDocument.status == DocumentStatus.ACTIVE)
            .where(
                text(
                    "to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,'')) @@ plainto_tsquery('simple', :q)"
                )
            )
            .order_by(text("score DESC"))
            .limit(limit)
            .offset(offset)
        )
        bind = {"q": query}
        if filters and filters.get("doc_type"):
            stmt = stmt.where(KnowledgeDocument.doc_type == filters["doc_type"])

        result = await session.execute(stmt, bind)
        rows = result.fetchall()
        return [
            DocumentResult(
                id=str(row[0]),
                title=row[1] or "",
                snippet=self._make_snippet(row[2] or "", query),
                score=float(row[5]) if row[5] is not None else 0.0,
                doc_type=str(row[3] or ""),
                metadata={
                    "id": str(row[0]),
                    "title": row[1] or "",
                    "doc_type": str(row[3] or ""),
                    "status": str(row[4] or ""),
                },
            )
            for row in rows
        ]

    async def _search_like(
        self,
        session: AsyncSession,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        offset: int,
    ) -> List[DocumentResult]:
        """Fallback LIKE-based search when FTS5 is unavailable."""
        like = f"%{query}%"
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.status == DocumentStatus.ACTIVE)
            .where(
                KnowledgeDocument.title.ilike(like)
                | KnowledgeDocument.content.ilike(like)
            )
            .order_by(KnowledgeDocument.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if filters and filters.get("doc_type"):
            stmt = stmt.where(KnowledgeDocument.doc_type == filters["doc_type"])

        result = await session.execute(stmt)
        docs = list(result.scalars().all())
        return [
            DocumentResult(
                id=str(d.id),
                title=d.title or "",
                snippet=self._make_snippet(d.content or "", query),
                score=1.0,
                doc_type=d.doc_type.value if d.doc_type else "",
                metadata={
                    "id": str(d.id),
                    "title": d.title or "",
                    "doc_type": d.doc_type.value if d.doc_type else "",
                    "status": d.status.value if d.status else "",
                },
            )
            for d in docs
        ]

    @staticmethod
    def _make_snippet(content: str, query: str, context_chars: int = 150) -> str:
        """Extract a relevant text snippet around the first match."""
        if not content or not query:
            return (content or "")[:context_chars]
        idx = content.lower().find(query.lower())
        if idx == -1:
            return content[:context_chars]
        start = max(0, idx - context_chars // 2)
        end = min(len(content), idx + len(query) + context_chars // 2)
        snippet = content[start:end].replace("\n", " ")
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet


# Module-level convenience instance
_fts: Optional[FullTextSearch] = None


def get_fulltext_search() -> FullTextSearch:
    """Return a singleton FullTextSearch instance."""
    global _fts
    if _fts is None:
        _fts = FullTextSearch()
    return _fts
