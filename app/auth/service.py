"""Auth service — orchestrates registration, login, permission checks.

Business logic between API layer and auth repositories.
All methods are async and follow the Repository pattern.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any, Dict, Optional, Set, Union

from sqlalchemy import select

from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.models import PERMISSION_CODES, Permission, Role
from app.auth.repository import (
    RoleRepository,
    TenantRepository,
    UserRepository,
)


class AuthService:
    """Auth business logic service.

    Args:
        user_repo: Optional UserRepository override.
        role_repo: Optional RoleRepository override.
        tenant_repo: Optional TenantRepository override.
    """

    def __init__(
        self,
        user_repo: Optional[UserRepository] = None,
        role_repo: Optional[RoleRepository] = None,
        tenant_repo: Optional[TenantRepository] = None,
    ):
        self._user_repo = user_repo
        self._role_repo = role_repo
        self._tenant_repo = tenant_repo

    def _hash_password(self, password: str) -> str:
        """Hash a password using PBKDF2-SHA256.

        Returns format: pbkdf2:sha256:100000:<salt>:<hash>

        Args:
            password: Raw password.

        Returns:
            Hashed password string.
        """
        salt = secrets.token_hex(16)
        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return f"pbkdf2:sha256:100000:{salt}:{hash_bytes.hex()}"

    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against stored hash.

        Args:
            password: Raw password to check.
            hashed: Stored hash (pbkdf2:sha256:iterations:salt:hash).

        Returns:
            True if password matches.
        """
        try:
            parts = hashed.split(":")
            if len(parts) != 5 or parts[0] != "pbkdf2":
                return False
            _, algo, iterations_str, salt, stored_hash = parts
            iterations = int(iterations_str)
            computed = hashlib.pbkdf2_hmac(
                algo,
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            ).hex()
            return secrets.compare_digest(computed, stored_hash)
        except (ValueError, IndexError):
            return False

    async def register_user(
        self,
        session,
        *,
        username: str,
        password: str,
        email: Optional[str] = None,
        tenant_id: Optional[Union[str, str]] = None,
    ) -> Dict[str, Any]:
        """Register a new user with hashed password.

        Args:
            session: AsyncSession.
            username: Unique username.
            password: Raw password (will be hashed).
            email: Optional email.
            tenant_id: Optional tenant UUID.

        Returns:
            User dict without password.

        Raises:
            ValueError: If username already exists.
        """
        from app.auth.repository import UserRepository

        repo = self._user_repo or UserRepository(session)
        existing = await repo.find_by_username(username)
        if existing is not None:
            raise ValueError(f"Username '{username}' already exists")

        hashed = self._hash_password(password)

        user = await repo.create_user(
            username=username,
            hashed_password=hashed,
            email=email,
            tenant_id=tenant_id,
        )
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        }

    async def authenticate_user(
        self,
        session,
        *,
        username: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """Authenticate user by username/password.

        Args:
            session: AsyncSession.
            username: Username.
            password: Raw password.

        Returns:
            User dict (without password) if authenticated, else None.
        """
        from app.auth.repository import UserRepository

        repo = self._user_repo or UserRepository(session)
        user = await repo.find_by_username(username)
        if user is None or not user.is_active:
            return None

        if not self._verify_password(password, user.hashed_password):
            return None

        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "roles": [r.name for r in (user.roles or [])],
        }

    async def create_access_token_for_user(
        self,
        session,
        *,
        username: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """Authenticate and create JWT access + refresh tokens.

        Args:
            session: AsyncSession.
            username: Username.
            password: Raw password.

        Returns:
            Dict with access_token, refresh_token and user info, or None.
        """
        user_data = await self.authenticate_user(session, username=username, password=password)
        if user_data is None:
            return None

        claims = {
            "sub": user_data["id"],
            "username": user_data["username"],
            "tenant_id": user_data.get("tenant_id") or "",
            "roles": user_data.get("roles", []),
        }
        access = create_access_token(data=claims, expires_delta=timedelta(hours=1))
        refresh = create_refresh_token(data=claims)
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "user": user_data,
        }

    async def refresh_tokens(
        self,
        session,
        *,
        refresh_token: str,
    ) -> Optional[Dict[str, Any]]:
        """Issue a new access (+ refresh) token pair from a refresh token."""
        from app.auth.jwt import decode_refresh_token
        from app.auth.repository import UserRepository

        payload = decode_refresh_token(refresh_token)
        if payload is None:
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        repo = self._user_repo or UserRepository(session)
        user = await repo.get_user(user_id)
        if user is None or not user.is_active:
            return None
        user_data = {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "roles": [r.name for r in (user.roles or [])],
        }
        claims = {
            "sub": user_data["id"],
            "username": user_data["username"],
            "tenant_id": user_data.get("tenant_id") or "",
            "roles": user_data.get("roles", []),
        }
        return {
            "access_token": create_access_token(data=claims),
            "refresh_token": create_refresh_token(data=claims),
            "token_type": "bearer",
            "user": user_data,
        }

    async def get_user_permissions(
        self,
        session,
        user_id: Union[str, str],
    ) -> Set[str]:
        """Get all permission codes for a user.

        Args:
            session: AsyncSession.
            user_id: User UUID.

        Returns:
            Set of permission code strings.
        """
        repo = self._user_repo or UserRepository(session)
        user = await repo.get_user(user_id)
        if user is None:
            return set()

        permissions: Set[str] = set()
        for role in user.roles or []:
            for perm in role.permissions or []:
                permissions.add(perm.code)
        return permissions

    async def has_permission(
        self,
        session,
        user_id: Union[str, str],
        permission_code: str,
    ) -> bool:
        """Check if a user has a specific permission.

        Args:
            session: AsyncSession.
            user_id: User UUID.
            permission_code: Permission code string.

        Returns:
            True if the user has the permission.
        """
        permissions = await self.get_user_permissions(session, user_id)
        return permission_code in permissions

    async def seed_default_roles_and_permissions(
        self,
        session,
    ) -> None:
        """Seed default roles and permissions for first-time setup.

        Args:
            session: AsyncSession.
        """
        from app.auth.repository import RoleRepository

        role_repo = self._role_repo or RoleRepository(session)

        # Create permissions if they don't exist
        existing_perms = {}
        for code, desc in PERMISSION_CODES.items():
            stmt = select(Permission).where(Permission.code == code)
            result = await session.execute(stmt)
            perm = result.scalar_one_or_none()
            if perm is None:
                perm = Permission(code=code, description=desc)
                session.add(perm)
                await session.flush()
            existing_perms[code] = perm

        from app.auth.models import role_permissions

        async def _link_role_perms(role: Role, perms: list) -> None:
            for perm in perms:
                await session.execute(
                    role_permissions.insert().values(role_id=role.id, permission_id=perm.id)
                )
            await session.flush()

        admin_role = await role_repo.find_by_name("admin")
        if admin_role is None:
            admin_role = await role_repo.create_role(
                name="admin", description="System administrator - all permissions"
            )
            await _link_role_perms(admin_role, list(existing_perms.values()))

        editor_role = await role_repo.find_by_name("editor")
        if editor_role is None:
            editor_role = await role_repo.create_role(
                name="editor", description="Editor - read/write knowledge base"
            )
            await _link_role_perms(
                editor_role,
                [
                    existing_perms[c]
                    for c in ("knowledge.read", "knowledge.write", "knowledge.delete")
                    if c in existing_perms
                ],
            )

        viewer_role = await role_repo.find_by_name("viewer")
        if viewer_role is None:
            viewer_role = await role_repo.create_role(
                name="viewer", description="Viewer - read-only knowledge base"
            )
            if "knowledge.read" in existing_perms:
                await _link_role_perms(viewer_role, [existing_perms["knowledge.read"]])
