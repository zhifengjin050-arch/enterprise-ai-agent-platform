"""Knowledge management API routes.

CRUD operations for knowledge documents via KnowledgeRepository.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.knowledge.models import DocumentStatus
from app.knowledge.repository import KnowledgeRepository

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class DocumentCreateRequest(BaseModel):
    """Request body for creating a knowledge document."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    format: str = "markdown"
    doc_type: Optional[str] = "OTHER"
    source: str = "api"
    source_url: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None


class DocumentUpdateRequest(BaseModel):
    """Request body for updating a knowledge document."""

    title: Optional[str] = None
    content: Optional[str] = None
    doc_type: Optional[str] = None
    status: Optional[str] = None
    author: Optional[str] = None
    quality_score: Optional[float] = None


@router.post("/documents")
async def create_document(
    body: DocumentCreateRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new knowledge document."""
    repo = KnowledgeRepository(session)
    doc = await repo.create_document(
        title=body.title,
        content=body.content,
        format=body.format,
        doc_type=body.doc_type,
        status=DocumentStatus.DRAFT,
        source=body.source,
        source_url=body.source_url,
        author=body.author,
        metadata_json=body.metadata_json,
        tag_names=body.tags,
    )
    return {"message": "Document created", "document": KnowledgeRepository.to_dict(doc)}


@router.get("/documents")
async def list_documents(
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List knowledge documents."""
    repo = KnowledgeRepository(session)
    status_enum = DocumentStatus(status) if status else None
    docs = await repo.list_documents(
        status=status_enum,
        doc_type=doc_type,
        limit=limit,
        offset=offset,
    )
    return {
        "results": [KnowledgeRepository.to_dict(d) for d in docs],
        "total": len(docs),
        "limit": limit,
        "offset": offset,
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a single document by UUID."""
    repo = KnowledgeRepository(session)
    doc = await repo.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return KnowledgeRepository.to_dict(doc)


@router.put("/documents/{document_id}")
async def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing document."""
    repo = KnowledgeRepository(session)
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] is not None:
        fields["status"] = DocumentStatus(fields["status"])
    doc = await repo.update_document(document_id, **fields)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document updated", "document": KnowledgeRepository.to_dict(doc)}


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    hard: bool = Query(False),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Archive (default) or hard-delete a document."""
    repo = KnowledgeRepository(session)
    ok = await repo.delete_document(document_id, hard=hard)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "message": "Document deleted" if hard else "Document archived",
        "document_id": document_id,
    }


@router.get("/search")
async def search_documents(
    q: str = Query("", description="Search query"),
    doc_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Search knowledge documents (repository list + title/content filter)."""
    from app.knowledge.searcher import search

    results = await search(
        session,
        query=q,
        doc_type=doc_type,
        limit=limit,
        offset=offset,
    )
    return {
        "query": q,
        "results": [KnowledgeRepository.to_dict(r.document) for r in results],
        "total": len(results),
        "limit": limit,
        "offset": offset,
    }


@router.get("/categories")
async def list_categories(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """List all knowledge categories."""
    repo = KnowledgeRepository(session)
    categories = await repo.list_categories()
    return {
        "categories": [
            {
                "id": str(c.id),
                "name": c.name,
                "description": c.description,
                "parent_id": str(c.parent_id) if c.parent_id else None,
            }
            for c in categories
        ]
    }


@router.post("/categories")
async def create_category(
    name: str,
    description: Optional[str] = None,
    parent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new category."""
    repo = KnowledgeRepository(session)
    category = await repo.get_or_create_category(name, description, parent_id)
    return {
        "message": "Category created",
        "category": {
            "id": str(category.id),
            "name": category.name,
            "description": category.description,
        },
    }


@router.get("/tags")
async def list_tags(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """List all tags."""
    repo = KnowledgeRepository(session)
    tags = await repo.list_tags()
    return {"tags": [{"id": str(t.id), "name": t.name, "description": t.description} for t in tags]}


@router.post("/documents/{document_id}/tags")
async def assign_tags(
    document_id: str,
    tags: List[str],
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Assign tags to a document."""
    from app.knowledge.tagger import add_tags_to_document

    try:
        doc = await add_tags_to_document(session, document_id, tags)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "message": "Tags assigned",
        "document_id": document_id,
        "tags": [t.name for t in doc.tags],
    }


@router.get("/stats")
async def get_knowledge_stats(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get knowledge base statistics."""
    repo = KnowledgeRepository(session)
    docs = await repo.list_documents(limit=1000)
    categories = await repo.list_categories()
    tags = await repo.list_tags()
    by_type: Dict[str, int] = {}
    for doc in docs:
        key = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
        by_type[key] = by_type.get(key, 0) + 1
    return {
        "total_documents": len(docs),
        "total_categories": len(categories),
        "total_tags": len(tags),
        "by_type": by_type,
    }


# ──────────────────────────────────────────────
# Phase 5 — Knowledge Intelligence Layer APIs
# ──────────────────────────────────────────────


class IntelligenceSearchRequest(BaseModel):
    """Request body for hybrid intelligence search."""

    query: str = Field(..., min_length=1, description="Search query")
    top_n: int = Field(5, ge=1, le=50, description="Results after rerank")
    recall_k: int = Field(20, ge=1, le=100, description="TopK recall before rerank")
    use_graph: bool = Field(True, description="Enable knowledge graph boost")
    use_rerank: bool = Field(True, description="Enable reranker")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")


@router.post("/search")
async def intelligence_search(
    body: IntelligenceSearchRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Hybrid intelligence search: Vector + BM25 + Graph → Rerank → TopN.

    Phase 5 endpoint.  Complements GET /search (simple ILIKE search).
    """
    from app.knowledge.retrieval import KnowledgeRetriever

    retriever = KnowledgeRetriever(recall_k=body.recall_k, top_n=body.top_n)
    results = await retriever.retrieve(
        body.query,
        top_n=body.top_n,
        recall_k=body.recall_k,
        filters=body.filters,
        use_graph=body.use_graph,
        use_rerank=body.use_rerank,
        session=session,
    )
    return {
        "query": body.query,
        "results": [r.to_dict() for r in results],
        "total": len(results),
        "top_n": body.top_n,
        "recall_k": body.recall_k,
    }


@router.get("/entities/{entity_id}")
async def get_knowledge_entity(
    entity_id: str,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a knowledge graph entity by ID."""
    from app.knowledge.graph import KnowledgeGraph

    kg = KnowledgeGraph(session)
    node = await kg.get_entity(entity_id, session=session)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return node.to_dict()


@router.get("/graph/{entity_id}")
async def get_knowledge_graph(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a knowledge subgraph centred on an entity."""
    from app.knowledge.graph import KnowledgeGraph

    kg = KnowledgeGraph(session)
    subgraph = await kg.get_subgraph(entity_id, depth=depth, session=session)
    if not subgraph.get("nodes"):
        raise HTTPException(
            status_code=404,
            detail=f"Entity '{entity_id}' not found or has empty subgraph",
        )
    return subgraph


@router.post("/documents/{document_id}/intelligence")
async def process_document_intelligence_api(
    document_id: str,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Run Intelligence Layer processing (chunk + embed + graph) on a document."""
    from app.knowledge.intelligence import process_document_intelligence

    repo = KnowledgeRepository(session)
    doc = await repo.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await process_document_intelligence(
        session,
        document_id=str(doc.id),
        title=doc.title or "",
        content=doc.content or "",
    )
    await session.commit()
    return {"message": "Intelligence processing complete", **result}
