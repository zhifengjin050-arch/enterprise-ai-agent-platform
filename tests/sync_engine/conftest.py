"""Shared fixtures for sync_engine tests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import app as fastapi_app

# Import models so Base.metadata is complete
import app.auth.models  # noqa: F401
import app.connector.models  # noqa: F401
import app.sync_engine.models  # noqa: F401
import app.task.models  # noqa: F401

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.sync_modes import SyncResult


class FakeConnector(BaseConnector):
    """Deterministic connector for sync engine tests."""

    name: str = "Fake"
    connector_type: str = "fake"

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
        documents: Optional[List[ConnectorDocument]] = None,
        fail: bool = False,
    ) -> None:
        super().__init__(config=config)
        self._documents = documents or []
        self._fail = fail

    async def test_connection(self) -> bool:
        return not self._fail

    async def fetch_documents(self) -> List[ConnectorDocument]:
        return list(self._documents)

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        for doc in self._documents:
            if doc.id == document_id:
                return doc
        return None

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> SyncResult:
        if self._fail:
            raise ConnectionError("Simulated connector failure")

        docs = list(self._documents)
        if sync_mode == "incremental" and cursor:
            docs = [d for d in docs if d.updated_at and d.updated_at > cursor]

        next_cursor = cursor
        for doc in docs:
            if doc.updated_at and (next_cursor is None or doc.updated_at > next_cursor):
                next_cursor = doc.updated_at

        return SyncResult.from_documents(docs, next_cursor=next_cursor, has_more=False)


@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite engine with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    reset_engine()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    """Yield an AsyncSession bound to the test engine."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def api_client(db_engine):
    """FastAPI test client with DB override."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def sample_documents() -> List[ConnectorDocument]:
    """Three sample documents with increasing timestamps."""
    return [
        ConnectorDocument(
            id="doc-1",
            title="Doc One",
            content="# One",
            url="https://example.com/1",
            updated_at="2026-01-01T00:00:00Z",
            metadata={"source": "test"},
        ),
        ConnectorDocument(
            id="doc-2",
            title="Doc Two",
            content="# Two",
            url="https://example.com/2",
            updated_at="2026-02-01T00:00:00Z",
            metadata={"source": "test"},
        ),
        ConnectorDocument(
            id="doc-3",
            title="Doc Three",
            content="# Three",
            url="https://example.com/3",
            updated_at="2026-03-01T00:00:00Z",
            metadata={"source": "test"},
        ),
    ]