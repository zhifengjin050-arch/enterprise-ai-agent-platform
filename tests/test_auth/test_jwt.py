"""Tests for JWT token creation and decoding."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.auth.jwt import create_access_token, decode_access_token


class TestJWT:
    """Test JWT token creation and validation."""

    def test_create_token(self) -> None:
        """Test creating a valid JWT token."""
        token = create_access_token(
            data={
                "sub": "user-uuid-123",
                "username": "testuser",
                "roles": ["admin"],
            }
        )
        assert isinstance(token, str)
        assert len(token) > 20
        assert token.count(".") == 2  # JWT has 3 parts

    def test_decode_valid_token(self) -> None:
        """Test decoding a valid token."""
        token = create_access_token(
            data={
                "sub": "user-uuid-456",
                "username": "johndoe",
                "tenant_id": "tenant-uuid-789",
            }
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-uuid-456"
        assert payload["username"] == "johndoe"
        assert payload["tenant_id"] == "tenant-uuid-789"

    def test_decode_expired_token(self) -> None:
        """Test decoding an expired token returns None."""
        token = create_access_token(
            data={"sub": "test"},
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        payload = decode_access_token(token)
        assert payload is None

    def test_decode_invalid_token(self) -> None:
        """Test decoding garbage returns None."""
        payload = decode_access_token("invalid-token-string")
        assert payload is None

    def test_token_with_roles(self) -> None:
        """Test token includes role information."""
        token = create_access_token(
            data={
                "sub": "user-1",
                "username": "admin_user",
                "roles": ["admin", "editor"],
            }
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert "admin" in payload.get("roles", [])
        assert "editor" in payload.get("roles", [])