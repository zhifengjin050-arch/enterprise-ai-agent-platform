"""Tests for the Request ID middleware.

Verifies that:
1. Every response has an X-Request-ID header
2. The ID is available as request.state.request_id
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.middleware.request_id import RequestIDMiddleware


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware."""

    async def test_sets_request_id_on_state(self) -> None:
        """Middleware should attach request_id to request.state."""
        middleware = RequestIDMiddleware(MagicMock())  # type: ignore[arg-type]

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        async def call_next(req: Request) -> JSONResponse:
            assert hasattr(req.state, "request_id")
            assert len(req.state.request_id) == 36  # UUID v4 length
            return JSONResponse({"ok": True})

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    async def test_sets_x_request_id_header(self) -> None:
        """Middleware should set X-Request-ID response header."""
        middleware = RequestIDMiddleware(MagicMock())  # type: ignore[arg-type]

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        async def call_next(req: Request) -> JSONResponse:
            return JSONResponse({"ok": True})

        response = await middleware.dispatch(request, call_next)
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36


class TestRequestIDMiddlewareIntegration:
    """Integration test with a FastAPI app."""

    @pytest.fixture
    def app(self) -> "FastAPI":
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request) -> dict:
            return {"request_id": request.state.request_id}

        return app

    def test_integration(self, app: FastAPI) -> None:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        data = response.json()
        assert "request_id" in data
        assert data["request_id"] == response.headers["X-Request-ID"]
