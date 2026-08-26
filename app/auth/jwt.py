"""JWT token creation and decoding.

Uses python-jose for JWT operations with HS256 signing.
Supports access_token and refresh_token.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from app.core.config import get_settings

_JWT_SECRET: Optional[str] = None
_JWT_ALGORITHM = "HS256"
_ACCESS_EXPIRE_MINUTES = 60  # 1 hour
_REFRESH_EXPIRE_DAYS = 14


def _get_secret() -> str:
    """Get JWT secret from settings or environment.

    Security Note:
        The dev fallback is INSECURE and exists only for local development.
        In production, always set JWT_SECRET in .env or environment.
    """
    global _JWT_SECRET
    if _JWT_SECRET is None:
        import logging
        import os

        settings = get_settings()
        env_secret = os.environ.get("JWT_SECRET")
        config_secret = getattr(settings, "jwt_secret", None)

        if env_secret:
            _JWT_SECRET = env_secret
        elif config_secret and "dev-secret" not in config_secret:
            _JWT_SECRET = config_secret
        else:
            logging.getLogger(__name__).warning(
                "JWT_SECRET not configured! Using INSECURE dev fallback. "
                "Set JWT_SECRET in .env for production."
            )
            _JWT_SECRET = "dev-secret-do-not-use-in-production"
    return _JWT_SECRET


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token (type=access)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=_ACCESS_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, _get_secret(), algorithm=_JWT_ALGORITHM)


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token (type=refresh)."""
    to_encode = {
        "sub": data.get("sub"),
        "tenant_id": data.get("tenant_id", ""),
    }
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=_REFRESH_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, _get_secret(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token.

    Rejects refresh tokens when used as access tokens.
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_JWT_ALGORITHM])
        if payload.get("type") == "refresh":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a refresh token."""
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode any JWT without type filtering."""
    try:
        return jwt.decode(token, _get_secret(), algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return None
