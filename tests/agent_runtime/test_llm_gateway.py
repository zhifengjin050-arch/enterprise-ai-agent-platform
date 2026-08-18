"""Tests for LLM Gateway and ModelRouter."""

from __future__ import annotations

from typing import AsyncGenerator, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import LLMQuotaException
from app.llm.gateway import (
    LLMGateway,
    LLMProvider,
    ModelRouter,
    OpenAICompatibleProvider,
    TaskComplexity,
    build_default_router,
    get_llm_gateway,
)


class DummyProvider(LLMProvider):
    def __init__(self, name: str = "dummy", model: str = "m1") -> None:
        self.name = name
        self._model = model
        self.chat_calls = 0

    async def chat(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        self.chat_calls += 1
        return f"echo:{message}"

    async def stream(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        for part in ["a", "b"]:
            yield part

    async def embedding(self, texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2] for _ in texts]

    def get_model_name(self) -> str:
        return self._model


class QuotaProvider(DummyProvider):
    async def chat(self, message: str, **kwargs) -> str:
        raise RuntimeError("rate limit 429 quota exceeded")


class TestModelRouter:
    def test_register_and_list(self) -> None:
        router = ModelRouter()
        router.register("deepseek", DummyProvider("deepseek"))
        assert "deepseek" in router.list_providers()

    def test_route_simple_prefers_deepseek(self) -> None:
        router = ModelRouter()
        router.register("openai", DummyProvider("openai"))
        router.register("deepseek", DummyProvider("deepseek"))
        p = router.route(TaskComplexity.SIMPLE)
        assert p.name == "deepseek"

    def test_route_complex_prefers_claude(self) -> None:
        router = ModelRouter()
        router.register("deepseek", DummyProvider("deepseek"))
        router.register("claude", DummyProvider("claude"))
        p = router.route(TaskComplexity.COMPLEX)
        assert p.name == "claude"

    def test_route_embedding(self) -> None:
        router = ModelRouter()
        router.register("default", DummyProvider("default"))
        router.register("bge", DummyProvider("bge"))
        p = router.route(TaskComplexity.EMBEDDING)
        assert p.name == "bge"

    def test_route_string_complexity(self) -> None:
        router = ModelRouter()
        router.register("deepseek", DummyProvider("deepseek"))
        p = router.route("simple")
        assert p.name == "deepseek"

    def test_route_unknown_string(self) -> None:
        router = ModelRouter()
        router.register("deepseek", DummyProvider("deepseek"))
        p = router.route("weird")
        assert p.name == "deepseek"

    def test_route_empty_falls_back(self) -> None:
        router = ModelRouter()
        p = router.route(TaskComplexity.SIMPLE)
        assert p is not None

    def test_route_any_when_only_one(self) -> None:
        router = ModelRouter()
        router.register("only", DummyProvider("only"))
        p = router.route(TaskComplexity.COMPLEX)
        assert p.name == "only"

    def test_build_default_router(self) -> None:
        router = build_default_router()
        assert "default" in router.list_providers()
        assert "deepseek" in router.list_providers()
        assert "openai" in router.list_providers()


class TestLLMGateway:
    @pytest.mark.asyncio
    async def test_chat(self) -> None:
        router = ModelRouter()
        router.register("deepseek", DummyProvider("deepseek"))
        gw = LLMGateway(router)
        ans = await gw.chat("hi")
        assert ans == "echo:hi"
        assert gw.get_model_name() == "m1"

    @pytest.mark.asyncio
    async def test_stream(self) -> None:
        router = ModelRouter()
        router.register("deepseek", DummyProvider("deepseek"))
        gw = LLMGateway(router)
        chunks = []
        async for c in gw.stream("x"):
            chunks.append(c)
        assert chunks == ["a", "b"]

    @pytest.mark.asyncio
    async def test_embedding(self) -> None:
        router = ModelRouter()
        router.register("embedding", DummyProvider("embedding"))
        gw = LLMGateway(router)
        vecs = await gw.embedding(["a", "b"])
        assert len(vecs) == 2

    @pytest.mark.asyncio
    async def test_quota_exception(self) -> None:
        router = ModelRouter()
        router.register("deepseek", QuotaProvider("deepseek"))
        gw = LLMGateway(router)
        with pytest.raises(LLMQuotaException):
            await gw.chat("x")

    @pytest.mark.asyncio
    async def test_complex_routing(self) -> None:
        router = ModelRouter()
        deep = DummyProvider("deepseek")
        claude = DummyProvider("claude", model="claude-3")
        router.register("deepseek", deep)
        router.register("claude", claude)
        gw = LLMGateway(router)
        await gw.chat("x", complexity=TaskComplexity.COMPLEX)
        assert claude.chat_calls == 1
        assert deep.chat_calls == 0

    def test_get_llm_gateway_singleton(self) -> None:
        a = get_llm_gateway()
        b = get_llm_gateway()
        assert a is b

    def test_task_complexity_values(self) -> None:
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.COMPLEX.value == "complex"
        assert TaskComplexity.EMBEDDING.value == "embedding"


class TestOpenAICompatibleProvider:
    @pytest.mark.asyncio
    async def test_wraps_client(self) -> None:
        client = MagicMock()
        client.chat = AsyncMock(return_value="ok")
        client.chat_stream = MagicMock()
        client.get_model_name = MagicMock(return_value="gpt")

        async def _gen(*a, **k):
            yield "x"
            return

        client.chat_stream = _gen
        provider = OpenAICompatibleProvider(name="openai", client=client)
        assert await provider.chat("hi") == "ok"
        assert provider.get_model_name() == "gpt"
        chunks = [c async for c in provider.stream("hi")]
        assert chunks == ["x"]
