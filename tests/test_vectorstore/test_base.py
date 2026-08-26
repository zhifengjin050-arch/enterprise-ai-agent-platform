"""Tests for VectorStore abstract interface and VectorSearchResult."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.vectorstore.base import VectorSearchResult, VectorStore


class TestVectorSearchResult:
    """Verify VectorSearchResult dataclass."""

    def test_minimal_creation(self) -> None:
        result = VectorSearchResult(id="e1", document_id="d1", score=0.95)
        assert result.id == "e1"
        assert result.document_id == "d1"
        assert result.score == 0.95
        assert result.metadata == {}
        assert result.content is None

    def test_full_creation(self) -> None:
        result = VectorSearchResult(
            id="e1",
            document_id="d1",
            score=0.92,
            metadata={"title": "Test Doc", "doc_type": "sop"},
            content="# Test\ncontent here",
        )
        assert result.metadata["title"] == "Test Doc"
        assert result.content is not None


class TestVectorStoreInterface:
    """Verify that VectorStore defines the expected contract."""

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            VectorStore()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self) -> None:
        class IncompleteStore(VectorStore):
            async def add(
                self,
                document_id: str,
                embedding: List[float],
                metadata: Optional[Dict[str, Any]] = None,
                content: Optional[str] = None,
            ) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteStore()

    def test_valid_implementation(self) -> None:
        class ValidStore(VectorStore):
            async def add(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def add_batch(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def query(self, *args: Any, **kwargs: Any) -> List[VectorSearchResult]:
                return []

            async def delete(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def delete_batch(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def update(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def count(self) -> int:
                return 0

        store = ValidStore()
        assert store is not None
