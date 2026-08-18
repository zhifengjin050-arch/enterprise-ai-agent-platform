"""
LLM service package.

Provides a unified interface for LLM interactions.
Supports multiple providers through the abstract base class.

Exports:
    - LLMService: Abstract base class
    - OpenAICompatibleLLM: Universal OpenAI-compatible provider
    - DeepSeekLLM: DeepSeek-specific provider
    - llm_client: Global default LLM client instance
    - Cache utilities: hash_prompt, hash_document, cached_call, etc.
"""

from app.llm.base import LLMService

# Cache utilities
from app.llm.cache import (
    cached_call,
    clear_cache,
    configure_cache,
    get_cache,
    get_cache_stats,
    hash_document,
    hash_prompt,
    set_cache,
    store_cached_result,
)
from app.llm.client import OpenAICompatibleLLM, llm_client
from app.llm.deepseek import DeepSeekLLM

# Gateway (Phase 6) — lazy-safe re-exports
from app.llm.gateway import (
    LLMGateway,
    LLMProvider,
    ModelRouter,
    TaskComplexity,
    get_llm_gateway,
)

__all__ = [
    "LLMService",
    "OpenAICompatibleLLM",
    "DeepSeekLLM",
    "llm_client",
    "hash_prompt",
    "hash_document",
    "cached_call",
    "store_cached_result",
    "get_cache",
    "set_cache",
    "clear_cache",
    "configure_cache",
    "get_cache_stats",
    "LLMGateway",
    "LLMProvider",
    "ModelRouter",
    "TaskComplexity",
    "get_llm_gateway",
]
