"""Tests for AuthService."""

from __future__ import annotations

import hashlib
import secrets
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.models import User
from app.auth.service import AuthService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    return AsyncMock()


class TestAuthService:
    """Test AuthService business logic."""

    def _hash_password(self, password: str) -> str:
        """Create PBKDF2 hash matching the service method."""
        salt = secrets.token_hex(16)
        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        return f"pbkdf2:sha256:100000:{salt}:{hash_bytes.hex()}"

    async def test_authenticate_user_success(self, mock_session: AsyncMock) -> None:
        """Test successful user authentication."""
        hashed = self._hash_password("correct_password")

        mock_user = MagicMock(spec=User)
        mock_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.hashed_password = hashed
        mock_user.tenant_id = None
        mock_user.roles = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        result = await service.authenticate_user(
            mock_session,
            username="testuser",
            password="correct_password",
        )
        assert result is not None
        assert result["username"] == "testuser"

    async def test_authenticate_user_wrong_password(self, mock_session: AsyncMock) -> None:
        """Test authentication with wrong password."""
        hashed = self._hash_password("correct_password")

        mock_user = MagicMock(spec=User)
        mock_user.is_active = True
        mock_user.hashed_password = hashed
        mock_user.roles = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        result = await service.authenticate_user(
            mock_session,
            username="testuser",
            password="wrong_password",
        )
        assert result is None

    async def test_authenticate_user_inactive(self, mock_session: AsyncMock) -> None:
        """Test authentication with inactive user returns None."""
        mock_user = MagicMock(spec=User)
        mock_user.is_active = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        result = await service.authenticate_user(
            mock_session,
            username="inactive_user",
            password="any",
        )
        assert result is None

    async def test_login_flow(self, mock_session: AsyncMock) -> None:
        """Test full login flow returns token."""
        hashed = self._hash_password("pwd123")

        mock_user = MagicMock(spec=User)
        mock_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_user.username = "login_user"
        mock_user.email = None
        mock_user.is_active = True
        mock_user.hashed_password = hashed
        mock_user.tenant_id = None
        mock_user.roles = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        result = await service.create_access_token_for_user(
            mock_session,
            username="login_user",
            password="pwd123",
        )
        assert result is not None
        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert result["user"]["username"] == "login_user"

    async def test_register_user_success(self, mock_session: AsyncMock) -> None:
        """Test successful user registration."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_create_result = MagicMock()
        mock_create_result.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_create_result.username = "newuser"
        mock_create_result.email = "new@example.com"
        mock_create_result.is_active = True
        mock_create_result.tenant_id = None

        mock_repo = AsyncMock()
        mock_repo.find_by_username = AsyncMock(return_value=None)
        mock_repo.create_user = AsyncMock(return_value=mock_create_result)

        service = AuthService(user_repo=mock_repo)
        result = await service.register_user(
            mock_session,
            username="newuser",
            password="secure123",
            email="new@example.com",
        )
        assert result["username"] == "newuser"
        assert result["email"] == "new@example.com"
        assert "hashed_password" not in result  # Must not expose password

    async def test_register_duplicate_username(self, mock_session: AsyncMock) -> None:
        """Test registration with existing username raises ValueError."""
        mock_existing = MagicMock(spec=User)
        mock_existing.username = "existing"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        with pytest.raises(ValueError, match="already exists"):
            await service.register_user(
                mock_session,
                username="existing",
                password="pwd",
            )

    async def test_has_permission(self, mock_session: AsyncMock) -> None:
        """Test permission check."""
        mock_perm = MagicMock()
        mock_perm.code = "knowledge.read"

        mock_role = MagicMock()
        mock_role.permissions = [mock_perm]

        mock_user = MagicMock(spec=User)
        mock_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_user.roles = [mock_role]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        result = await service.has_permission(
            mock_session,
            "550e8400-e29b-41d4-a716-446655440000",
            "knowledge.read",
        )
        assert result is True

    async def test_has_permission_missing(self, mock_session: AsyncMock) -> None:
        """Test permission check returns False when missing."""
        mock_user = MagicMock(spec=User)
        mock_user.roles = []  # No roles

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = AuthService()
        result = await service.has_permission(
            mock_session,
            "550e8400-e29b-41d4-a716-446655440000",
            "admin",
        )
        assert result is False
