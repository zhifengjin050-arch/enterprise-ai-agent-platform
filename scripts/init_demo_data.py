#!/usr/bin/env python3
"""Initialize enterprise demo data.

Imports markdown documents from demo/documents/ into the
knowledge base, triggers chunking, embedding, and knowledge graph extraction.

Usage:
    cd enterprise-knowledge-agent
    python scripts/init_demo_data.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import frontmatter

from app.db.session import get_session_factory
from app.knowledge.intelligence import process_document_intelligence
from app.knowledge.models import DocType, DocumentStatus
from app.knowledge.repository import KnowledgeRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("init_demo_data")

DEMO_DIR = ROOT / "demo" / "documents"

DOC_TYPE_MAP: dict[str, DocType] = {
    "SOP": DocType.SOP,
    "INCIDENT": DocType.INCIDENT,
    "BEST_PRACTICE": DocType.BEST_PRACTICE,
    "ARCHITECTURE": DocType.ARCHITECTURE,
    "CONFIGURATION": DocType.CONFIGURATION,
    "OTHER": DocType.OTHER,
}


async def import_document(
    repo: KnowledgeRepository,
    md_path: Path,
) -> dict:
    """Import a single markdown file into the knowledge base."""
    post = frontmatter.load(str(md_path))

    title: str = post.get("title") or md_path.stem
    doc_type_str: str = post.get("doc_type", "OTHER")
    raw_tags: list = post.get("tags") or []
    tags = [t.strip() for t in raw_tags if t and t.strip()]
    author: str | None = post.get("author")
    content: str = post.content

    if not content.strip():
        logger.warning("Skipping empty document: %s", md_path.name)
        return {"path": str(md_path), "skipped": True}

    doc_type = DOC_TYPE_MAP.get(doc_type_str.upper(), DocType.OTHER)

    version_raw = post.get("version")
    metadata: dict = {}
    if version_raw is not None:
        try:
            metadata["version"] = str(version_raw)
        except (ValueError, TypeError):
            pass

    logger.info("Importing: %s (%s / %s)", title, doc_type.value, tags)

    doc = await repo.create_document(
        title=title,
        content=content,
        format="markdown",
        doc_type=doc_type,
        status=DocumentStatus.PUBLISHED,
        source="local",
        author=author,
        metadata_json=metadata if metadata else None,
        tag_names=tags if tags else None,
    )

    logger.info("  → Document created: %s", doc.id)

    try:
        result = await process_document_intelligence(
            repo.session,
            document_id=str(doc.id),
            title=title,
            content=content,
            embed=True,
            build_graph=True,
        )
        logger.info(
            "  → Intelligence: chunks=%d entities=%d relations=%d",
            result.get("chunk_count", 0),
            result.get("entity_count", 0),
            result.get("relation_count", 0),
        )
    except Exception as exc:
        logger.warning("  → Intelligence skipped: %s", exc)
        result = {"chunk_count": 0, "entity_count": 0, "relation_count": 0}

    return {
        "path": md_path.name,
        "title": title,
        "doc_type": doc_type.value,
        "tags": tags,
        "document_id": str(doc.id),
        "chunk_count": result.get("chunk_count", 0),
        "entity_count": result.get("entity_count", 0),
        "relation_count": result.get("relation_count", 0),
    }


async def main() -> None:
    """Run the full demo data import."""
    md_files = sorted(DEMO_DIR.glob("*.md"))
    if not md_files:
        logger.warning("No markdown files found in %s", DEMO_DIR)
        return

    logger.info("Found %d demo documents to import", len(md_files))
    logger.info("=" * 60)

    factory = get_session_factory()
    results: list[dict] = []

    async with factory() as session:
        repo = KnowledgeRepository(session)

        for md_path in md_files:
            result = await import_document(repo, md_path)
            results.append(result)

        await session.commit()

    logger.info("=" * 60)
    logger.info("Import complete!")

    total_chunks = sum(r.get("chunk_count", 0) for r in results)
    total_entities = sum(r.get("entity_count", 0) for r in results)
    total_relations = sum(r.get("relation_count", 0) for r in results)

    for r in results:
        skipped = " [SKIPPED]" if r.get("skipped") else ""
        logger.info(
            "  %s → %s (chunks=%d entities=%d relations=%d)%s",
            r.get("path", "?"),
            r.get("title", "?"),
            r.get("chunk_count", 0),
            r.get("entity_count", 0),
            r.get("relation_count", 0),
            skipped,
        )

    logger.info(
        "Summary: %d docs, %d chunks, %d entities, %d relations",
        len(results),
        total_chunks,
        total_entities,
        total_relations,
    )


if __name__ == "__main__":
    asyncio.run(main())
