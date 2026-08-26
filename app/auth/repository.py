"""Auth repository — database access layer for User, Role, Permission, Tenant.

All auth persistence goes through these repositories.
API and service layers must not execute raw ORM queries directly.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Permission, Role, Tenant, User


def _as_uuid(value: Union[str, uuid.UUID]) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class UserRepository:
    """Async repository for User CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(
        self,
        *,
        username: str,
        hashed_password: str,
        email: Optional[str] = None,
        is_active: bool = True,
        tenant_id: Optional[Union[str, uuid.UUID]] = None,
        user_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> User:
        user = User(
            id=_as_uuid(user_id) if user_id else uuid.uuid4(),
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=is_active,
            tenant_id=_as_uuid(tenant_id) if tenant_id else None,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["roles"])
        return user

    async def get_user(self, user_id: Union[str, uuid.UUID]) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == _as_uuid(user_id))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.username == username)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(
        self, *, tenant_id: Optional[Union[str, uuid.UUID]] = None, limit: int = 50, offset: int = 0
    ) -> List[User]:
        stmt = select(User).options(selectinload(User.roles))
        if tenant_id is not None:
            stmt = stmt.where(User.tenant_id == _as_uuid(tenant_id))
        stmt = stmt.order_by(User.username).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_user(self, user_id: Union[str, uuid.UUID], **fields: Any) -> Optional[User]:
        user = await self.get_user(user_id)
        if user is None:
            return None
        for key, value in fields.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def add_role_to_user(
        self, user_id: Union[str, uuid.UUID], role_id: Union[str, uuid.UUID]
    ) -> bool:
        user = await self.get_user(user_id)
        role_stmt = select(Role).where(Role.id == _as_uuid(role_id))
        role_result = await self.session.execute(role_stmt)
        role = role_result.scalar_one_or_none()
        if user is None or role is None:
            return False
        if role not in user.roles:
            user.roles.append(role)
            await self.session.flush()
        return True


class RoleRepository:
    """Async repository for Role CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_role(self, *, name: str, description: Optional[str] = None) -> Role:
        role = Role(name=name, description=description)
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_role(self, role_id: Union[str, uuid.UUID]) -> Optional[Role]:
        stmt = (
            select(Role).options(selectinload(Role.permissions)).where(Role.id == _as_uuid(role_id))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Optional[Role]:
        stmt = select(Role).options(selectinload(Role.permissions)).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_permission_to_role(
        self, role_id: Union[str, uuid.UUID], permission_id: Union[str, uuid.UUID]
    ) -> bool:
        role_stmt = (
            select(Role).options(selectinload(Role.permissions)).where(Role.id == _as_uuid(role_id))
        )
        role_result = await self.session.execute(role_stmt)
        role = role_result.scalar_one_or_none()
        perm_stmt = select(Permission).where(Permission.id == _as_uuid(permission_id))
        perm_result = await self.session.execute(perm_stmt)
        permission = perm_result.scalar_one_or_none()
        if role is None or permission is None:
            return False
        if permission not in role.permissions:
            role.permissions.append(permission)
            await self.session.flush()
        return True


class TenantRepository:
    """Async repository for Tenant CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_tenant(self, *, name: str, description: Optional[str] = None) -> Tenant:
        tenant = Tenant(name=name, description=description)
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def get_tenant(self, tenant_id: Union[str, uuid.UUID]) -> Optional[Tenant]:
        stmt = select(Tenant).where(Tenant.id == _as_uuid(tenant_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Optional[Tenant]:
        stmt = select(Tenant).where(Tenant.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_tenants(self) -> List[Tenant]:
        result = await self.session.execute(select(Tenant).order_by(Tenant.name))
        return list(result.scalars().all())
