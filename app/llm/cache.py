"""LLM call cache to avoid redundant API calls.

Supports caching based on:
- Prompt hash: full prompt + system prompt hash
- Document hash: document content hash (independent of prompt)

Uses an in-memory LRU cache by default.
Can be extended to Redis or database-backed storage.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

# Cache entry with expiry — OrderedDict enables deterministic LRU eviction
_cache_store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_cache_max_size: int = 1000
_cache_ttl: int = 3600  # 1 hour default


def _make_hash_key(*parts: str) -> str:
    """Create a SHA-256 hash key from string parts.

    Args:
        *parts: String components to hash.

    Returns:
        Hex digest string.
    """
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def hash_prompt(
    prompt: str,
    system_prompt: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> str:
    """Create a cache key hash from a prompt configuration.

    Args:
        prompt: The user message / task description.
        system_prompt: Optional system instruction.
        schema: Optional JSON schema dict.
        model: Optional model identifier.

    Returns:
        Cache key hash string.
    """
    parts = [prompt]
    if system_prompt:
        parts.append(system_prompt)
    if schema:
        parts.append(json.dumps(schema, sort_keys=True))
    if model:
        parts.append(model)
    return _make_hash_key(*parts)


def hash_document(content: str, title: Optional[str] = None) -> str:
    """Create a cache key hash from document content.

    This is useful for caching LLM calls that process the same
    document content (e.g., classification, tagging).

    Args:
        content: Document markdown content.
        title: Optional document title.

    Returns:
        Cache key hash string.
    """
    parts = [content]
    if title:
        parts.append(title)
    return _make_hash_key(*parts)


def get_cache(key: str) -> Optional[Any]:
    """Retrieve a cached value by key.

    Args:
        key: Cache key hash string.

    Returns:
        Cached value, or None if not found or expired.
    """
    entry = _cache_store.get(key)
    if entry is None:
        return None

    # Check expiry
    if entry.get("expires_at", 0) < time.time():
        del _cache_store[key]
        return None

    # Move to end for LRU ordering
    _cache_store.move_to_end(key)

    return entry.get("value")


def set_cache(
    key: str,
    value: Any,
    ttl: Optional[int] = None,
) -> None:
    """Store a value in cache with TTL.

    Args:
        key: Cache key hash string.
        value: Value to cache.
        ttl: Time-to-live in seconds. Defaults to _cache_ttl.
    """
    # Evict oldest (first inserted) if at capacity — OrderedDict FIFO
    if len(_cache_store) >= _cache_max_size:
        try:
            _cache_store.popitem(last=False)
        except KeyError:
            pass

    _cache_store[key] = {
        "value": value,
        "created_at": time.time(),
        "expires_at": time.time() + (ttl if ttl is not None else _cache_ttl),
    }
    _cache_store.move_to_end(key)


def cached_call(
    prompt: str,
    system_prompt: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    use_content_hash: bool = False,
    content: Optional[str] = None,
    content_title: Optional[str] = None,
) -> Tuple[Optional[str], bool]:
    """Check if a cached result exists for the given prompt/document.

    Returns:
        Tuple of (cached_value, hit) where hit is True if cache had a value.
    """
    if use_content_hash and content:
        key = hash_document(content, content_title)
    else:
        key = hash_prompt(prompt, system_prompt, schema, model)

    value = get_cache(key)
    return (value, value is not None)


def store_cached_result(
    prompt: str,
    result: Any,
    system_prompt: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    use_content_hash: bool = False,
    content: Optional[str] = None,
    content_title: Optional[str] = None,
    ttl: Optional[int] = None,
) -> str:
    """Store a result in cache and return the cache key.

    Args:
        prompt: The prompt used (or content for content-hash mode).
        result: The result value to cache.
        system_prompt: Optional system instruction.
        schema: Optional JSON schema dict.
        model: Optional model identifier.
        use_content_hash: If True, key is based on content rather than prompt.
        content: Document content for content-hash mode.
        content_title: Document title for content-hash mode.
        ttl: Time-to-live in seconds.

    Returns:
        The cache key that was used.
    """
    if use_content_hash and content:
        key = hash_document(content, content_title)
    else:
        key = hash_prompt(prompt, system_prompt, schema, model)

    set_cache(key, result, ttl=ttl)
    return key


def clear_cache() -> None:
    """Clear all cached entries."""
    _cache_store.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics.

    Returns:
        Dict with size, max_size, ttl info.
    """
    return {
        "size": len(_cache_store),
        "max_size": _cache_max_size,
        "ttl_seconds": _cache_ttl,
    }


def configure_cache(max_size: int = 1000, ttl: int = 3600) -> None:
    """Configure cache parameters.

    Args:
        max_size: Maximum number of entries in the cache.
        ttl: Default time-to-live in seconds.
    """
    global _cache_max_size, _cache_ttl
    _cache_max_size = max_size
    _cache_ttl = ttl
