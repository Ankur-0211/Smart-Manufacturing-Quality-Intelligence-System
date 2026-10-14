"""Request correlation middleware (pure ASGI so SSE streaming is never buffered).

- Accepts a well-formed ``X-Request-ID`` or generates one; echoes it on the response.
- Stores ``request_id`` and ``started_at`` on ``request.state`` for the envelope.
- Binds ``request_id`` into structlog context and logs one line per request.
"""

from __future__ import annotations

import re
import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.ids import new_id
from app.core.logging import get_logger

REQUEST_ID_HEADER = "x-request-id"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

log = get_logger("app.request")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = next(
            (
                value.decode("latin-1")
                for key, value in scope.get("headers", [])
                if key.decode("latin-1").lower() == REQUEST_ID_HEADER
            ),
            None,
        )
        request_id = incoming if incoming and _SAFE_REQUEST_ID.match(incoming) else new_id()
        started = time.perf_counter()
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["started_at"] = started

        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode("latin-1"), request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info(
                "request",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_holder.get("status"),
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
            )
            structlog.contextvars.clear_contextvars()
