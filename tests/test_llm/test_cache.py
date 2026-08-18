"""Tests for LLM cache (app/llm/cache.py).

All tests run without real LLM calls.
"""

from __future__ import annotations

import time

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


def teardown_function() -> None:
    clear_cache()
    configure_cache(max_size=1000, ttl=3600)  # Reset config to defaults


class TestHashPrompt:
    def test_hash_consistency(self) -> None:
        """Same inputs should produce the same hash."""
        h1 = hash_prompt("Classify this document", system_prompt="You are a classifier.")
        h2 = hash_prompt("Classify this document", system_prompt="You are a classifier.")
        assert h1 == h2

    def test_hash_different_inputs(self) -> None:
        """Different inputs should produce different hashes."""
        h1 = hash_prompt("Classify this")
        h2 = hash_prompt("Tag this document")
        assert h1 != h2

    def test_hash_with_schema(self) -> None:
        """Hash should incorporate schema dict."""
        schema = {"type": "object", "properties": {"doc_type": {"type": "string"}}}
        h = hash_prompt("Test", schema=schema)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest


class TestHashDocument:
    def test_document_hash_consistency(self) -> None:
        """Same content should produce the same hash."""
        h1 = hash_document("# Kubernetes Deployment\n\nSteps...", title="Deploy")
        h2 = hash_document("# Kubernetes Deployment\n\nSteps...", title="Deploy")
        assert h1 == h2

    def test_document_hash_different(self) -> None:
        """Different content should produce different hashes."""
        h1 = hash_document("Content A")
        h2 = hash_document("Content B")
        assert h1 != h2

    def test_document_hash_without_title(self) -> None:
        """Hash should work without a title."""
        h = hash_document("Just content")
        assert isinstance(h, str)
        assert len(h) == 64


class TestCacheOperations:
    def test_set_and_get(self) -> None:
        """Should store and retrieve values."""
        set_cache("key1", {"result": "ok"})
        value = get_cache("key1")
        assert value == {"result": "ok"}

    def test_get_missing(self) -> None:
        """Missing key should return None."""
        assert get_cache("nonexistent") is None

    def test_cache_expiry(self) -> None:
        """Expired entry should return None."""
        set_cache("temp", "value", ttl=0)  # 0 seconds TTL → immediate expiry
        time.sleep(0.01)
        assert get_cache("temp") is None

    def test_cache_max_size_eviction(self) -> None:
        """Should evict oldest when at capacity."""
        clear_cache()  # Ensure clean state (other modules may have polluted cache)
        configure_cache(max_size=3, ttl=3600)
        set_cache("a", 1)
        set_cache("b", 2)
        set_cache("c", 3)
        set_cache("d", 4)  # Should evict 'a'
        assert get_cache("a") is None
        assert get_cache("b") == 2
        assert get_cache("d") == 4

    def test_clear_cache(self) -> None:
        """Clear should remove all entries."""
        set_cache("x", 100)
        set_cache("y", 200)
        clear_cache()
        assert get_cache("x") is None
        assert get_cache("y") is None

    def test_cache_stats(self) -> None:
        """Stats should reflect current state."""
        clear_cache()
        configure_cache(max_size=500, ttl=1800)
        stats = get_cache_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 500
        assert stats["ttl_seconds"] == 1800


class TestCachedCall:
    def test_cached_call_prompt_miss(self) -> None:
        """First call should miss cache."""
        value, hit = cached_call(prompt="Classify X")
        assert not hit
        assert value is None

    def test_cached_call_prompt_hit(self) -> None:
        """After storing, second call should hit cache."""
        store_cached_result(
            prompt="Classify X",
            result={"doc_type": "sop"},
        )
        value, hit = cached_call(prompt="Classify X")
        assert hit
        assert value == {"doc_type": "sop"}

    def test_cached_call_content_hash_miss(self) -> None:
        """Content-hash mode should miss on first call."""
        value, hit = cached_call(
            prompt="",
            use_content_hash=True,
            content="# Doc Content",
            content_title="Doc",
        )
        assert not hit
        assert value is None

    def test_cached_call_content_hash_hit(self) -> None:
        """After storing with content hash, second call should hit."""
        store_cached_result(
            prompt="",
            result={"tags": ["kubernetes", "docker"]},
            use_content_hash=True,
            content="# Doc Content",
            content_title="Doc",
        )
        value, hit = cached_call(
            prompt="",
            use_content_hash=True,
            content="# Doc Content",
            content_title="Doc",
        )
        assert hit
        assert value == {"tags": ["kubernetes", "docker"]}

    def test_store_returns_key(self) -> None:
        """store_cached_result should return the cache key."""
        key = store_cached_result(
            prompt="Test prompt",
            result={"ok": True},
        )
        assert isinstance(key, str)
        assert len(key) == 64