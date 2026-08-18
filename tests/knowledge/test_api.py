"""API tests for Knowledge Intelligence endpoints."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import app as fastapi_app

import app.auth.models  # noqa: F401
import app.connector.models  # noqa: F401
import app.entity.models  # noqa: F401
import app.knowledge.chunk_models  # noqa: F401
import app.knowledge.models  # noqa: F401
import app.relation.models  # noqa: F401
import app.sync_engine.models  # noqa: F401
import app.task.models  # noqa: F401


@pytest_asyncio.fixture
async def api_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()
    reset_engine()


class TestKnowledgeIntelligenceAPI:
    async def test_openapi_has_new_routes(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert "/api/knowledge/search" in paths
        # POST intelligence search
        assert "post" in paths["/api/knowledge/search"]
        assert "/api/knowledge/entities/{entity_id}" in paths
        assert "/api/knowledge/graph/{entity_id}" in paths

    async def test_post_search(self, api_client: AsyncClient) -> None:
        """POST /search returns intelligence results (retriever mocked)."""
        from unittest.mock import AsyncMock, patch

        from app.knowledge.retrieval import RetrievalResult

        fake_results = [
            RetrievalResult(
                document_id="d1",
                score=0.9,
                title="K8s",
                content="kubernetes guide",
                source="hybrid",
            )
        ]

        with patch(
            "app.knowledge.retrieval.KnowledgeRetriever.retrieve",
            new_callable=AsyncMock,
            return_value=fake_results,
        ):
            resp = await api_client.post(
                "/api/knowledge/search",
                json={"query": "kubernetes", "top_n": 3, "use_graph": False},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "kubernetes"
        assert len(data["results"]) == 1
        assert data["results"][0]["document_id"] == "d1"

    async def test_get_entity_not_found(self, api_client: AsyncClient) -> None:
        resp = await api_client.get(
            "/api/knowledge/entities/00000000-0000-0000-0000-000000000099"
        )
        assert resp.status_code == 404

    async def test_get_graph_not_found(self, api_client: AsyncClient) -> None:
        resp = await api_client.get(
            "/api/knowledge/graph/00000000-0000-0000-0000-000000000099"
        )
        assert resp.status_code == 404

    async def test_legacy_get_search_still_works(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/knowledge/search", params={"q": "test"})
        assert resp.status_code == 200
        assert "results" in resp.json()