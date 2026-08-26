"""Auth API endpoints: login, register, refresh, profile.

Provides JWT-based authentication and user management.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditEvent
from app.auth.dependencies import get_current_user
from app.auth.service import AuthService
from app.core.logging import get_logger
from app.db.session import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    """Login request body."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Registration request body."""

    username: str
    password: str
    email: Optional[str] = None
    # tenant_id ignored on public register (security) — admin assigns later


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login")
async def login(
    request_body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticate user and return JWT access + refresh tokens."""
    service = AuthService()
    result = await service.create_access_token_for_user(
        session,
        username=request_body.username,
        password=request_body.password,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        await AuditEvent(session).record(
            "auth.login",
            resource="user",
            resource_id=result["user"]["id"],
            tenant_id=result["user"].get("tenant_id"),
            user_id=result["user"]["id"],
            ip=getattr(request.state, "client_ip", None),
        )
    except Exception:
        logger.exception("Failed to record auth.login audit event")
    return result


@router.post("/register")
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new user account.

    Public registration does **not** accept arbitrary tenant_id
    (prevents cross-tenant join attacks).
    """
    service = AuthService()
    try:
        user = await service.register_user(
            session,
            username=request.username,
            password=request.password,
            email=request.email,
            tenant_id=None,
        )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/refresh")
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Exchange a refresh_token for a new access/refresh pair."""
    service = AuthService()
    result = await service.refresh_tokens(session, refresh_token=body.refresh_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return result


@router.get("/me")
async def get_profile(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current user profile."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return current_user
