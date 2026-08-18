"""Auth ORM models: User, Role, Permission, Tenant.

Role-Based Access Control (RBAC) with multi-tenant support.

Relationships:
    User <-> Role <-> Permission  (many-to-many via association tables)
    Tenant -> User, Tenant -> KnowledgeDocument, Tenant -> WorkflowRun, etc.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ---- Association tables ----

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# ---- Tenant ----

class Tenant(Base):
    """Enterprise tenant for multi-tenant isolation."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ---- User ----

class User(Base):
    """Platform user with RBAC roles."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users"
    )
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant")


class Role(Base):
    """Named role in the RBAC hierarchy."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User", secondary=user_roles, back_populates="roles"
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )


class Permission(Base):
    """Granular permission code for RBAC."""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )


# Predefined permission codes
PERMISSION_CODES = {
    "knowledge.read": "查看知识库文档",
    "knowledge.write": "创建和编辑知识库文档",
    "knowledge.delete": "删除知识库文档",
    "workflow.approve": "审核工作流审批",
    "workflow.manage": "管理工作流执行",
    "admin.llm": "查看LLM成本数据",
    "admin.users": "管理用户和角色",
    "admin.tenant": "管理租户配置",
    "connector.read": "查看连接器配置",
    "connector.write": "创建和编辑连接器配置",
    "connector.sync": "触发连接器同步",
    "agent.read": "查看 Agent 配置与历史",
    "agent.write": "创建和编辑 Agent",
    "agent.execute": "执行 Agent 任务与流式对话",
    "admin.manage": "平台超级管理（含用户/角色/配额/审计）",
    "audit.read": "查看审计日志",
    "quota.read": "查看配额状态",
    "apikey.manage": "管理 API Key",
}

# Register Organization table for FK from User.organization_id
import app.auth.organization  # noqa: E402,F401
