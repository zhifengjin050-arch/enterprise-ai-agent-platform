"""Tests for auth repositories (UserRepository, RoleRepository, TenantRepository)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.models import Role, Tenant, User
from app.auth.repository import RoleRepository, TenantRepository, UserRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestUserRepository:
    """Test UserRepository CRUD operations."""

    async def test_create_user(self, mock_session: AsyncMock) -> None:
        """Test creating a user."""
        repo = UserRepository(mock_session)
        user = await repo.create_user(
            username="newuser",
            hashed_password="hashed",
            email="new@example.com",
        )
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert user.username == "newuser"

    async def test_find_by_username_found(self, mock_session: AsyncMock) -> None:
        """Test finding user by username — found."""
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.username = "existing"
        mock_user.roles = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        repo = UserRepository(mock_session)
        user = await repo.find_by_username("existing")
        assert user is not None
        assert user.username == "existing"

    async def test_find_by_username_not_found(self, mock_session: AsyncMock) -> None:
        """Test finding user by username — not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = UserRepository(mock_session)
        user = await repo.find_by_username("nonexistent")
        assert user is None

    async def test_get_user(self, mock_session: AsyncMock) -> None:
        """Test getting user by ID."""
        user_id = uuid.uuid4()
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.roles = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        repo = UserRepository(mock_session)
        user = await repo.get_user(str(user_id))
        assert user is not None

    async def test_add_role_to_user(self, mock_session: AsyncMock) -> None:
        """Test adding role to user."""
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        mock_user = MagicMock(spec=User)
        mock_user.roles = []
        mock_role = MagicMock(spec=Role)
        mock_role.id = role_id

        # First execute returns user, second returns role
        mock_result_user = MagicMock()
        mock_result_user.scalar_one_or_none.return_value = mock_user

        mock_result_role = MagicMock()
        mock_result_role.scalar_one_or_none.return_value = mock_role

        mock_session.execute = AsyncMock(side_effect=[mock_result_user, mock_result_role])

        repo = UserRepository(mock_session)
        result = await repo.add_role_to_user(str(user_id), str(role_id))
        assert result is True
        assert mock_role in mock_user.roles


class TestRoleRepository:
    """Test RoleRepository CRUD operations."""

    async def test_create_role(self, mock_session: AsyncMock) -> None:
        """Test creating a role."""
        repo = RoleRepository(mock_session)
        role = await repo.create_role(name="viewer", description="Can view")
        mock_session.add.assert_called_once()
        assert role.name == "viewer"

    async def test_find_by_name(self, mock_session: AsyncMock) -> None:
        """Test finding role by name."""
        mock_role = MagicMock(spec=Role)
        mock_role.name = "admin"
        mock_role.permissions = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute.return_value = mock_result

        repo = RoleRepository(mock_session)
        role = await repo.find_by_name("admin")
        assert role is not None
        assert role.name == "admin"


class TestTenantRepository:
    """Test TenantRepository CRUD operations."""

    async def test_create_tenant(self, mock_session: AsyncMock) -> None:
        """Test creating a tenant."""
        repo = TenantRepository(mock_session)
        tenant = await repo.create_tenant(name="test-org")
        mock_session.add.assert_called_once()
        assert tenant.name == "test-org"

    async def test_find_by_name(self, mock_session: AsyncMock) -> None:
        """Test finding tenant by name."""
        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.name = "acme"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_session.execute.return_value = mock_result

        repo = TenantRepository(mock_session)
        tenant = await repo.find_by_name("acme")
        assert tenant is not None
        assert tenant.name == "acme"

    async def test_list_tenants(self, mock_session: AsyncMock) -> None:
        """Test listing all tenants."""
        mock_tenant1 = MagicMock(spec=Tenant)
        mock_tenant1.name = "org1"
        mock_tenant2 = MagicMock(spec=Tenant)
        mock_tenant2.name = "org2"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_tenant1, mock_tenant2]
        mock_session.execute.return_value = mock_result

        repo = TenantRepository(mock_session)
        tenants = await repo.list_tenants()
        assert len(tenants) == 2
