"""Authentication & RBAC package.

Provides JWT-based user authentication, role-based access control,
multi-tenant isolation, and permission management for the enterprise
knowledge platform.
"""

from app.auth.dependencies import get_current_tenant, get_current_user, require_permission
from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.auth.models import Permission, Role, Tenant, User
from app.auth.organization import Organization, OrganizationType
from app.auth.rbac import PermissionChecker
from app.auth.repository import RoleRepository, TenantRepository, UserRepository
from app.auth.service import AuthService

__all__ = [
    "User",
    "Role",
    "Permission",
    "Tenant",
    "Organization",
    "OrganizationType",
    "UserRepository",
    "RoleRepository",
    "TenantRepository",
    "AuthService",
    "PermissionChecker",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    "get_current_user",
    "require_permission",
    "get_current_tenant",
]
