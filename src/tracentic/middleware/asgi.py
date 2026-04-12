"""ASGI middleware that injects per-request attributes into the global context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .._global_context import TracenticGlobalContext

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class TracenticMiddleware:
    """ASGI middleware that injects per-request attributes into the
    global context for the duration of a single HTTP request, then
    restores the previous values.

    Example::

        from tracentic.middleware.asgi import TracenticMiddleware

        app = TracenticMiddleware(
            app,
            request_attributes=lambda scope: {
                "user_id": scope.get("headers", {}).get("x-user-id"),
                "method": scope.get("method"),
            },
        )
    """

    __slots__ = ("_app", "_request_attributes")

    def __init__(
        self,
        app: ASGIApp,
        *,
        request_attributes: Callable[[Scope], dict[str, Any]],
    ) -> None:
        self._app = app
        self._request_attributes = request_attributes

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        global_ctx = TracenticGlobalContext.current
        attributes = self._request_attributes(scope)

        if not attributes:
            await self._app(scope, receive, send)
            return

        # Snapshot current values for the keys we're about to set
        current_all = global_ctx.get_all()
        snapshot: dict[str, Any] = {}
        for key in attributes:
            snapshot[key] = current_all.get(key)  # None if not present

        # Apply per-request attributes
        for key, value in attributes.items():
            if value is not None:
                global_ctx.set(key, value)
            else:
                global_ctx.remove(key)

        try:
            await self._app(scope, receive, send)
        finally:
            # Restore previous values
            for key, prev in snapshot.items():
                if prev is not None:
                    global_ctx.set(key, prev)
                else:
                    global_ctx.remove(key)
