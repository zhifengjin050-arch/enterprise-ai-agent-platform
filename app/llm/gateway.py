"""LLM Gateway — unified multi-provider facade for Agent Runtime.

Does not replace existing LLMService clients; wraps them behind
LLMProvider + ModelRouter.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.core.exceptions import LLMQuotaException
from app.llm.base import LLMService
from app.llm.client import OpenAICompatibleLLM, llm_client

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Routing hint for ModelRouter."""

    SIMPLE = "simple"
    COMPLEX = "complex"
    EMBEDDING = "embedding"


class LLMProvider(ABC):
    """Abstract provider interface used by the gateway."""

    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        ...

    @abstractmethod
    async def stream(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        ...
        yield  # pragma: no cover

    @abstractmethod
    async def embedding(self, texts: List[str]) -> List[List[float]]:
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        ...


class OpenAICompatibleProvider(LLMProvider):
    """Wraps an OpenAI-compatible LLMService as LLMProvider."""

    def __init__(
        self,
        *,
        name: str = "openai",
        client: Optional[LLMService] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.name = name
        if client is not None:
            self._client = client
        else:
            self._client = OpenAICompatibleLLM(
                api_key=api_key,
                base_url=base_url,
                model=model,
            )

    async def chat(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        return await self._client.chat(
            message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def stream(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._client.chat_stream(
            message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    async def embedding(self, texts: List[str]) -> List[List[float]]:
        """Delegate to app.embedding when available; otherwise empty vectors."""
        try:
            from app.embedding.client import OpenAICompatibleEmbedding

            provider = OpenAICompatibleEmbedding()
            return await provider.embed_documents(texts)
        except Exception as exc:
            logger.warning("Embedding via provider failed: %s", exc)
            return [[] for _ in texts]

    def get_model_name(self) -> str:
        return self._client.get_model_name()


class ModelRouter:
    """Select provider / model based on task complexity."""

    def __init__(self, providers: Optional[Dict[str, LLMProvider]] = None) -> None:
        self._providers: Dict[str, LLMProvider] = providers or {}

    def register(self, key: str, provider: LLMProvider) -> None:
        self._providers[key] = provider

    def route(self, complexity: TaskComplexity | str = TaskComplexity.SIMPLE) -> LLMProvider:
        """Pick a provider for the given complexity.

        Defaults:
            simple → deepseek (or default)
            complex → openai / claude if registered else default
            embedding → embedding provider
        """
        if isinstance(complexity, str):
            try:
                complexity = TaskComplexity(complexity)
            except ValueError:
                complexity = TaskComplexity.SIMPLE

        preferred: List[str]
        if complexity == TaskComplexity.COMPLEX:
            preferred = ["claude", "openai", "gpt", "qwen", "deepseek", "default"]
        elif complexity == TaskComplexity.EMBEDDING:
            preferred = ["embedding", "bge", "default"]
        else:
            preferred = ["deepseek", "qwen", "default", "openai"]

        for key in preferred:
            if key in self._providers:
                return self._providers[key]

        if self._providers:
            return next(iter(self._providers.values()))

        # Ultimate fallback
        return OpenAICompatibleProvider(name="default", client=llm_client)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())


class LLMGateway:
    """Unified entry point: chat / stream / embedding via ModelRouter."""

    def __init__(self, router: Optional[ModelRouter] = None) -> None:
        self._router = router or build_default_router()
        self._last_model: str = ""

    @property
    def router(self) -> ModelRouter:
        return self._router

    def get_model_name(self) -> str:
        return self._last_model or "unknown"

    async def chat(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        complexity: TaskComplexity | str = TaskComplexity.SIMPLE,
        session: Any = None,
        estimate_tokens: Optional[int] = None,
    ) -> str:
        # Tenant quota check (best-effort when session + tenant available)
        try:
            from app.quota.service import QuotaService
            from app.tenant.context import get_tenant_id

            tid = get_tenant_id()
            if tid and session is not None:
                await QuotaService(session).check_tokens(
                    tid, estimate_tokens or min(max_tokens, 512)
                )
        except LLMQuotaException:
            raise
        except Exception:
            pass

        provider = self._router.route(complexity)
        self._last_model = provider.get_model_name()
        try:
            answer = await provider.chat(
                message,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                from app.quota.service import QuotaService
                from app.tenant.context import get_tenant_id

                tid = get_tenant_id()
                if tid and session is not None:
                    await QuotaService(session).consume_tokens(
                        tid, estimate_tokens or min(max_tokens, 512)
                    )
            except Exception:
                pass
            return answer
        except Exception as exc:
            msg = str(exc).lower()
            if "quota" in msg or "rate limit" in msg or "429" in msg:
                raise LLMQuotaException(
                    message="LLM quota exceeded",
                    details={"provider": provider.name, "error": str(exc)},
                ) from exc
            raise

    async def stream(
        self,
        message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        complexity: TaskComplexity | str = TaskComplexity.SIMPLE,
    ) -> AsyncGenerator[str, None]:
        provider = self._router.route(complexity)
        self._last_model = provider.get_model_name()
        async for chunk in provider.stream(
            message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    async def embedding(
        self,
        texts: List[str],
        *,
        complexity: TaskComplexity | str = TaskComplexity.EMBEDDING,
    ) -> List[List[float]]:
        provider = self._router.route(complexity)
        return await provider.embedding(texts)


def build_default_router() -> ModelRouter:
    """Build router with DeepSeek / OpenAI-compatible defaults from settings."""
    from app.core.config import get_settings

    settings = get_settings()
    router = ModelRouter()

    default = OpenAICompatibleProvider(name="default", client=llm_client)
    router.register("default", default)
    router.register("deepseek", default)

    # Optional aliases pointing at same client with different logical names
    openai_provider = OpenAICompatibleProvider(
        name="openai",
        model=settings.llm_model,
        api_key=settings.llm_api_key or None,
        base_url=settings.llm_base_url or None,
    )
    router.register("openai", openai_provider)
    router.register("qwen", openai_provider)
    router.register("claude", openai_provider)
    router.register("embedding", default)
    router.register("bge", default)
    return router


_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
