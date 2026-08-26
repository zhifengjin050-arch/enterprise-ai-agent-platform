"""Security middleware — CORS headers, basic rate limit, IP capture."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Awaitable, Callable, Deque, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class SecurityMiddleware(BaseHTTPMiddleware):
    """Lightweight security layer for enterprise SaaS.

    Features:
        - CORS response headers (configurable origins)
        - Per-IP sliding-window rate limit
        - Client IP attached to request.state.client_ip
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_origins: Optional[list[str]] = None,
        rate_limit: int = 120,
        rate_window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.allowed_origins = allowed_origins or ["*"]
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_ip = self._client_ip(request)
        request.state.client_ip = client_ip

        # OPTIONS preflight
        if request.method == "OPTIONS":
            return self._cors(Response(status_code=204), request)

        if not self._allow(client_ip):
            resp = JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests",
                        "details": {"ip": client_ip},
                    },
                },
            )
            return self._cors(resp, request)

        response = await call_next(request)
        return self._cors(response, request)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _allow(self, ip: str) -> bool:
        now = time.monotonic()
        window = self._hits[ip]
        cutoff = now - self.rate_window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.rate_limit:
            return False
        window.append(now)
        return True

    def _cors(self, response: Response, request: Request) -> Response:
        origin = request.headers.get("Origin", "*")
        allow = (
            "*"
            if "*" in self.allowed_origins
            else (origin if origin in self.allowed_origins else self.allowed_origins[0])
        )
        response.headers["Access-Control-Allow-Origin"] = allow
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-API-Key, X-Tenant-ID, X-Organization-ID, X-Request-ID"
        )
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Tenant-ID"
        return response
