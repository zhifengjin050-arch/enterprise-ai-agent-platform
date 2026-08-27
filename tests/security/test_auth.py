"""Auth / JWT refresh tests."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.auth.service import AuthService


class TestJWTRefresh:
    def test_access_has_type(self) -> None:
        token = create_access_token({"sub": "u1"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload.get("type") == "access"

    def test_refresh_token_roundtrip(self) -> None:
        token = create_refresh_token({"sub": "u1", "tenant_id": "t1"})
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "u1"
        assert payload["type"] == "refresh"

    def test_refresh_cannot_be_used_as_access(self) -> None:
        token = create_refresh_token({"sub": "u1"})
        assert decode_access_token(token) is None

    def test_access_cannot_be_used_as_refresh(self) -> None:
        token = create_access_token({"sub": "u1"})
        assert decode_refresh_token(token) is None

    def test_expired_refresh(self) -> None:
        token = create_refresh_token({"sub": "u1"}, expires_delta=timedelta(seconds=-1))
        assert decode_refresh_token(token) is None

    @pytest.mark.parametrize("sub", ["a", "b", "c-uuid"])
    def test_access_subs(self, sub: str) -> None:
        assert decode_access_token(create_access_token({"sub": sub}))["sub"] == sub


class TestAuthServiceTokens:
    @pytest.mark.asyncio
    async def test_login_returns_refresh(self, db_session, tenant_user) -> None:
        svc = AuthService()
        result = await svc.create_access_token_for_user(
            db_session,
            username=tenant_user["user"].username,
            password=tenant_user["password"],
        )
        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        assert decode_access_token(result["access_token"]) is not None
        assert decode_refresh_token(result["refresh_token"]) is not None

    @pytest.mark.asyncio
    async def test_refresh_tokens(self, db_session, tenant_user) -> None:
        svc = AuthService()
        first = await svc.create_access_token_for_user(
            db_session,
            username=tenant_user["user"].username,
            password=tenant_user["password"],
        )
        second = await svc.refresh_tokens(db_session, refresh_token=first["refresh_token"])
        assert second is not None
        assert second["access_token"]
        assert second["user"]["id"] == str(tenant_user["user"].id)

    @pytest.mark.asyncio
    async def test_refresh_invalid(self, db_session) -> None:
        svc = AuthService()
        assert await svc.refresh_tokens(db_session, refresh_token="bad") is None

    @pytest.mark.asyncio
    async def test_bad_password(self, db_session, tenant_user) -> None:
        svc = AuthService()
        assert (
            await svc.create_access_token_for_user(
                db_session,
                username=tenant_user["user"].username,
                password="wrong",
            )
            is None
        )


class TestAuthAPI:
    @pytest.mark.asyncio
    async def test_login_api(self, api_client, tenant_user) -> None:
        # Need user in same DB as api_client — tenant_user uses db_session fixture
        # which is separate engine from api_client. Re-create via register+login path.
        reg = await api_client.post(
            "/api/auth/register",
            json={"username": "newuser1", "password": "pass12345", "email": "a@b.c"},
        )
        assert reg.status_code == 200
        login = await api_client.post(
            "/api/auth/login",
            json={"username": "newuser1", "password": "pass12345"},
        )
        assert login.status_code == 200
        body = login.json()
        assert "access_token" in body
        assert "refresh_token" in body

    @pytest.mark.asyncio
    async def test_register_ignores_tenant_id(self, api_client) -> None:
        resp = await api_client.post(
            "/api/auth/register",
            json={
                "username": "safeuser",
                "password": "pass12345",
                "tenant_id": "00000000-0000-0000-0000-000000000099",
            },
        )
        assert resp.status_code == 200
        assert resp.json().get("tenant_id") in (None, "")

    @pytest.mark.asyncio
    async def test_refresh_api(self, api_client) -> None:
        await api_client.post(
            "/api/auth/register",
            json={"username": "refuser", "password": "pass12345"},
        )
        login = await api_client.post(
            "/api/auth/login",
            json={"username": "refuser", "password": "pass12345"},
        )
        refresh = await api_client.post(
            "/api/auth/refresh",
            json={"refresh_token": login.json()["refresh_token"]},
        )
        assert refresh.status_code == 200
        assert refresh.json()["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_bad(self, api_client) -> None:
        resp = await api_client.post("/api/auth/refresh", json={"refresh_token": "x.y.z"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_requires_auth(self, api_client) -> None:
        resp = await api_client.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_openapi_has_refresh(self, api_client) -> None:
        paths = (await api_client.get("/openapi.json")).json()["paths"]
        assert "/api/auth/refresh" in paths
        assert "/api/auth/login" in paths

    @pytest.mark.asyncio
    async def test_register_disabled_in_production(self, api_client, monkeypatch) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "allow_register", None)
        resp = await api_client.post(
            "/api/auth/register",
            json={"username": "prodblock", "password": "pass12345"},
        )
        assert resp.status_code == 403
