"""Tests for the EmbeddingProvider abstract interface."""

from __future__ import annotations

from typing import List

import pytest

from app.embedding.base import EmbeddingProvider


class TestEmbeddingProviderInterface:
    """Verify that EmbeddingProvider defines the expected contract."""

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        """EmbeddingProvider should be abstract, not directly instantiable."""
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self) -> None:
        """A subclass missing any abstract method should fail instantiation."""

        class IncompleteProvider(EmbeddingProvider):
            async def embed_text(self, text: str) -> List[float]:
                return [0.1, 0.2]

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_concrete_subclass_success(self) -> None:
        """A minimal valid implementation."""

        class ValidProvider(EmbeddingProvider):
            async def embed_text(self, text: str) -> List[float]:
                return [0.1, 0.2] * 768

            async def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return [[0.1, 0.2] * 768 for _ in texts]

            async def get_dimension(self) -> int:
                return 1536

            async def close(self) -> None:
                return None

        provider = ValidProvider()
        assert provider is not None

    @pytest.mark.asyncio
    async def test_embed_text_returns_list_of_floats(self) -> None:
        """embed_text should return List[float]."""

        class TestProvider(EmbeddingProvider):
            async def embed_text(self, text: str) -> List[float]:
                return [0.5, 0.5]

            async def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return [[0.5, 0.5] for _ in texts]

            async def get_dimension(self) -> int:
                return 2

            async def close(self) -> None:
                return None

        provider = TestProvider()
        result = await provider.embed_text("hello")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_embed_documents_returns_correct_count(self) -> None:
        """embed_documents should return one vector per input text."""

        class TestProvider(EmbeddingProvider):
            async def embed_text(self, text: str) -> List[float]:
                return [0.5]

            async def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return [[0.5] for _ in texts]

            async def get_dimension(self) -> int:
                return 1

            async def close(self) -> None:
                return None

        provider = TestProvider()
        texts = ["a", "b", "c"]
        results = await provider.embed_documents(texts)
        assert len(results) == len(texts)