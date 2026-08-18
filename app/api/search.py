"""Search API routes.

Provides full-text, semantic, and hybrid search endpoints for
enterprise knowledge discovery. These are NOT chatbot RAG endpoints.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.search.fulltext import get_fulltext_search
from app.search.hybrid import get_hybrid_search
from app.search.indexer import get_indexer
from app.search.semantic import get_semantic_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
) -> Dict[str, Any]:
    """Semantic search using embedding + vector similarity."""
    try:
        engine = get_semantic_search()
        filters: Optional[Dict[str, str]] = None
        if doc_type:
            filters = {"doc_type": doc_type}
        results = await engine.search(query=q, top_k=top_k, filters=filters)
        return {
            "query": q,
            "mode": "semantic",
            "total": len(results),
            "top_k": top_k,
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "content": r.content[:500] if r.content else "",
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/fulltext")
async def fulltext_search(
    q: str = Query(..., min_length=1, description="Search query"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Full-text search using SQLite FTS5 / PostgreSQL FTS."""
    try:
        engine = get_fulltext_search()
        filters: Optional[Dict[str, str]] = None
        if doc_type:
            filters = {"doc_type": doc_type}
        results = await engine.search(query=q, filters=filters, limit=limit, offset=offset)
        return {
            "query": q,
            "mode": "fulltext",
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "snippet": r.snippet,
                    "score": r.score,
                    "doc_type": r.doc_type,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/hybrid")
async def hybrid_search(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Hybrid search combining full-text and semantic search via RRF."""
    try:
        engine = get_hybrid_search()
        results = await engine.search(query=q, top_k=top_k)
        return {
            "query": q,
            "mode": "hybrid",
            "total": len(results),
            "top_k": top_k,
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "snippet": r.snippet,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rebuild")
async def rebuild_index() -> Dict[str, Any]:
    """Rebuild the entire search index."""
    try:
        indexer = get_indexer()
        result = await indexer.rebuild_index()
        return {
            "action": "rebuild",
            "total": result.get("total", 0),
            "indexed": result.get("indexed", 0),
            "failed": result.get("failed", 0),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats")
async def search_stats() -> Dict[str, Any]:
    """Get search index statistics."""
    try:
        indexer = get_indexer()
        stats = await indexer.get_index_stats()
        return {
            "vector_indexed": stats.get("vector_indexed", 0),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
