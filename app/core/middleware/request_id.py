"""
Request ID middleware.

Generates a unique UUID for every incoming request and attaches it to:
- request.state.request_id (accessible in endpoint/handler code)
- response header X-Request-ID
- logging context (via the structured logger)
"""

from __future__ import annotations

import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to each request.

    The ID is available as ``request.state.request_id`` in handlers
    and is set on the response as the ``X-Request-ID`` header.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
