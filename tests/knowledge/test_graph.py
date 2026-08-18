"""Tests for Knowledge Graph adapters and DocumentChunk persistence."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import reset_engine
from app.entity.models import EntityType, KnowledgeEntity
from app.knowledge.chunk_models import DocumentChunk
from app.knowledge.chunk_repository import DocumentChunkRepository
from app.knowledge.chunking import Chunk, SmartChunker
from app.knowledge.graph import GraphEdge, GraphNode, KnowledgeGraph
from app.knowledge.memory import KnowledgeMemory
from app.knowledge.context_builder import IntelligenceContextBuilder
from app.knowledge.retrieval import RetrievalResult
from app.relation.models import KnowledgeRelation, RelationType

import app.auth.models  # noqa: F401
import app.connector.models  # noqa: F401
import app.entity.models  # noqa: F401
import app.knowledge.chunk_models  # noqa: F401
import app.knowledge.models  # noqa: F401
import app.relation.models  # noqa: F401
import app.sync_engine.models  # noqa: F401
import app.task.models  # noqa: F401


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
    reset_engine()


class TestGraphAdapters:
    def test_graph_node_from_entity(self) -> None:
        entity = KnowledgeEntity(
            name="Redis",
            entity_type=EntityType.TECHNOLOGY,
            description="Cache",
        )
        # id is auto-generated on flush; set manually for unit test
        import uuid

        entity.id = uuid.uuid4()
        node = GraphNode.from_entity(entity)
        assert node.name == "Redis"
        assert node.entity_type == "technology"
        d = node.to_dict()
        assert d["name"] == "Redis"

    def test_graph_edge_from_relation(self) -> None:
        import uuid

        rel = KnowledgeRelation(
            source_entity_id=uuid.uuid4(),
            target_entity_id=uuid.uuid4(),
            relation_type=RelationType.USES,
        )
        rel.id = uuid.uuid4()
        edge = GraphEdge.from_relation(rel)
        assert edge.relation_type == "uses"
        assert "source_id" in edge.to_dict()

    def test_entity_type_extensions(self) -> None:
        assert EntityType.ORGANIZATION.value == "organization"
        assert EntityType.PROJECT.value == "project"
        assert EntityType.SYSTEM.value == "system"
        assert EntityType.API.value == "api"


class TestDocumentChunks:
    async def test_save_and_list(self, db_session: AsyncSession) -> None:
        chunker = SmartChunker(max_tokens=256)
        chunks = chunker.chunk(
            "# Title\n\nHello world about Docker.",
            document_id="doc-abc",
            title="Title",
        )
        repo = DocumentChunkRepository(db_session)
        records = await repo.save_chunks(chunks)
        await db_session.commit()

        listed = await repo.list_by_document("doc-abc")
        assert len(listed) == len(records)
        assert listed[0].document_id == "doc-abc"
        assert listed[0].content

    async def test_delete_by_document(self, db_session: AsyncSession) -> None:
        repo = DocumentChunkRepository(db_session)
        await repo.save_chunks(
            [Chunk(document_id="doc-x", content="a", chunk_index=0, token_count=1)]
        )
        await db_session.commit()
        deleted = await repo.delete_by_document("doc-x")
        assert deleted == 1
        assert await repo.list_by_document("doc-x") == []


class TestMemoryAndContext:
    def test_knowledge_memory(self) -> None:
        mem = KnowledgeMemory(max_retrievals=2)
        mem.remember_retrieval("s1", "q1", [{"document_id": "d1"}])
        entry = mem.recall_retrieval("s1", "q1")
        assert entry is not None
        assert entry.results[0]["document_id"] == "d1"
        mem.clear_session("s1")
        assert mem.recall_retrieval("s1", "q1") is None

    def test_context_builder(self) -> None:
        builder = IntelligenceContextBuilder(max_tokens=500)
        results = [
            RetrievalResult(
                document_id="d1",
                title="Doc 1",
                content="Content about kubernetes",
                score=0.9,
            ),
            RetrievalResult(
                document_id="d2",
                title="Doc 2",
                content="More content",
                score=0.5,
            ),
        ]
        ctx = builder.build(results)
        assert len(ctx) >= 1
        text = builder.build_prompt_context(results)
        assert "Doc" in text


class TestKnowledgeGraphDB:
    async def test_get_entity_missing(self, db_session: AsyncSession) -> None:
        kg = KnowledgeGraph(db_session)
        assert await kg.get_entity("00000000-0000-0000-0000-000000000001") is None

    async def test_get_subgraph_missing(self, db_session: AsyncSession) -> None:
        kg = KnowledgeGraph(db_session)
        result = await kg.get_subgraph("00000000-0000-0000-0000-000000000001")
        assert result["nodes"] == []