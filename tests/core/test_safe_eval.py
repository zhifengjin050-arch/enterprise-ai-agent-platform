"""Tests for restricted workflow expressions."""

from __future__ import annotations

import pytest

from app.core.safe_eval import UnsafeExpressionError, safe_eval


def test_comparison_and_names() -> None:
    assert safe_eval("score > 0.5", {"score": 0.9}) is True
    assert safe_eval("score > 0.5", {"score": 0.1}) is False


def test_boolean_and_builtins() -> None:
    assert safe_eval("len(items) >= 2 and status == 'ok'", {"items": [1, 2], "status": "ok"})
    assert safe_eval("max(a, b) == 3", {"a": 1, "b": 3}) is True


def test_rejects_imports_and_calls() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("__import__('os').system('echo pwned')", {})
    with pytest.raises(UnsafeExpressionError):
        safe_eval("open('x')", {})
    with pytest.raises(UnsafeExpressionError):
        safe_eval("().__class__", {})


def test_production_jwt_secret_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "change-me-in-production")
    from app.core.config import Settings

    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(_env_file=None)
