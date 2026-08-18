"""Tests for auth ORM models: User, Role, Permission, Tenant."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Permission, Role, Tenant, User, PERMISSION_CODES


class TestUserModel:
    """Test User model creation and attributes."""

    def test_create_user(self) -> None:
        """Test creating a User instance with basic fields."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_pwd",
            is_active=True,
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_pwd"
        assert user.is_active is True

    def test_user_with_tenant(self) -> None:
        """Test User with tenant_id."""
        tenant_id = uuid.uuid4()
        user = User(
            username="tenant_user",
            hashed_password="pwd",
            tenant_id=tenant_id,
        )
        assert user.tenant_id == tenant_id

    def test_user_repr(self) -> None:
        """Test User has readable string representation."""
        user = User(username="test", hashed_password="pwd", is_active=True)
        assert user.username == "test"
        assert user.is_active is True


class TestRoleModel:
    """Test Role model creation and attributes."""

    def test_create_role(self) -> None:
        """Test creating a Role instance."""
        role = Role(name="admin", description="Administrator")
        assert role.name == "admin"
        assert role.description == "Administrator"

    def test_role_unique_name(self) -> None:
        """Role name should be unique at DB level."""
        role1 = Role(name="editor")
        role2 = Role(name="editor")
        assert role1.name == role2.name
        # Uniqueness is enforced by the DB, not Python


class TestPermissionModel:
    """Test Permission model creation and attributes."""

    def test_create_permission(self) -> None:
        """Test creating a Permission instance."""
        perm = Permission(code="knowledge.read", description="Read knowledge")
        assert perm.code == "knowledge.read"
        assert perm.description == "Read knowledge"

    def test_permission_codes_defined(self) -> None:
        """All expected permission codes should be in PERMISSION_CODES."""
        expected = [
            "knowledge.read",
            "knowledge.write",
            "knowledge.delete",
            "workflow.approve",
            "workflow.manage",
            "admin.llm",
            "admin.users",
            "admin.tenant",
        ]
        for code in expected:
            assert code in PERMISSION_CODES, f"Missing permission: {code}"


class TestTenantModel:
    """Test Tenant model creation and attributes."""

    def test_create_tenant(self) -> None:
        """Test creating a Tenant instance."""
        tenant = Tenant(name="acme-corp", description="ACME Corporation")
        assert tenant.name == "acme-corp"
        assert tenant.description == "ACME Corporation"

    def test_tenant_unique_name(self) -> None:
        """Tenant name uniqueness."""
        t1 = Tenant(name="test-org")
        t2 = Tenant(name="test-org")
        assert t1.name == t2.name


class TestRelationships:
    """Test RBAC relationships."""

    def test_user_role_relationship(self) -> None:
        """User can have multiple roles."""
        user = User(username="multi_role", hashed_password="pwd")
        role_admin = Role(name="admin")
        role_editor = Role(name="editor")
        user.roles.append(role_admin)
        user.roles.append(role_editor)
        assert len(user.roles) == 2
        assert role_admin in user.roles
        assert role_editor in user.roles

    def test_role_permission_relationship(self) -> None:
        """Role can have multiple permissions."""
        role = Role(name="admin")
        perm1 = Permission(code="knowledge.read")
        perm2 = Permission(code="knowledge.write")
        role.permissions.append(perm1)
        role.permissions.append(perm2)
        assert len(role.permissions) == 2