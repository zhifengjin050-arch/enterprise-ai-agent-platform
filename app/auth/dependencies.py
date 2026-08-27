"""FastAPI dependencies for auth and RBAC.

Provides dependency injection for:
- get_current_user: Extract and validate JWT from Authorization header.
- require_permission: Route-level permission guard.
- get_current_tenant: Extract tenant context from authenticated user.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.auth.service import AuthService
from app.db.session import get_db

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
    session: AsyncSession = Depends(get_db),
) -> Optional[Dict[str, Any]]:
    """Dependency that extracts the current user from JWT.

    Args:
        credentials: Bearer token from Authorization header.
        session: Database session.

    Returns:
        User dict (without password) or None for anonymous access.
    """
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    from app.auth.repository import UserRepository

    repo = UserRepository(session)
    user = await repo.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "roles": [r.name for r in (user.roles or [])],
    }


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
    session: AsyncSession = Depends(get_db),
) -> Optional[Dict[str, Any]]:
    """Dependency that returns current user or None (no auth error).

    Args:
        credentials: Bearer token.
        session: Database session.

    Returns:
        User dict or None.
    """
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    return payload


def require_permission(permission_code: str):
    """Dependency factory that requires a specific permission.

    Args:
        permission_code: The required permission code (e.g. 'knowledge.write').

    Returns:
        A FastAPI dependency function.
    """

    async def _check(
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> None:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        service = AuthService()
        has_perm = await service.has_permission(session, current_user["id"], permission_code)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission_code}",
            )

    return _check


async def get_current_tenant(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Optional[str]:
    """Dependency that extracts the tenant_id from the current user.

    Args:
        current_user: User dict from get_current_user.

    Returns:
        Tenant ID string or None.
    """
    if current_user is None:
        return None
    return current_user.get("tenant_id")


def _is_production() -> bool:
    from app.core.config import get_settings

    env = (get_settings().environment or "development").lower()
    return env in {"production", "prod"}


async def require_authenticated_in_production(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Optional[Dict[str, Any]]:
    """Production requires JWT; development/test remain open for demos and pytest."""
    if _is_production() and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
