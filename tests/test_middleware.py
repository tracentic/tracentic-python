"""Tests for the ASGI middleware — per-request global attribute scoping."""

from __future__ import annotations

from typing import Any

import pytest

from tracentic._global_context import TracenticGlobalContext
from tracentic.middleware.asgi import TracenticMiddleware


@pytest.fixture(autouse=True)
def _fresh_global_context() -> Any:
    # Each test starts with a pristine TracenticGlobalContext so we don't carry
    # state across tests and don't depend on a Tracentic client being built.
    TracenticGlobalContext._set_current(TracenticGlobalContext())
    yield
    TracenticGlobalContext._reset_current()


async def _call(
    middleware: TracenticMiddleware,
    scope_type: str = "http",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scope: dict[str, Any] = {"type": scope_type}
    if extra:
        scope.update(extra)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request"}

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    # Observed during the inner app's execution.
    observed: dict[str, Any] = {}

    async def app(s: dict[str, Any], r: Any, sn: Any) -> None:
        observed.update(TracenticGlobalContext.current.get_all())

    wrapped = TracenticMiddleware(app, request_attributes=middleware._request_attributes)
    await wrapped(scope, receive, send)
    return observed


async def test_request_attributes_applied_during_request() -> None:
    ctx = TracenticGlobalContext.current
    ctx.set("service", "api")

    observed: dict[str, Any] = {}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        observed.update(ctx.get_all())

    mw = TracenticMiddleware(
        app,
        request_attributes=lambda _s: {"user_id": "u-1", "method": "GET"},
    )
    await mw({"type": "http"}, _noop_receive, _noop_send)

    assert observed == {"service": "api", "user_id": "u-1", "method": "GET"}


async def test_attributes_restored_after_request() -> None:
    ctx = TracenticGlobalContext.current
    ctx.set("service", "api")

    mw = TracenticMiddleware(
        lambda s, r, sn: _noop(),
        request_attributes=lambda _s: {"user_id": "u-1", "service": "override"},
    )
    await mw({"type": "http"}, _noop_receive, _noop_send)

    # Original `service` value is restored; the transient `user_id` is removed.
    assert ctx.get_all() == {"service": "api"}


async def test_restore_runs_on_exception() -> None:
    ctx = TracenticGlobalContext.current
    ctx.set("service", "api")

    async def failing(scope: Any, receive: Any, send: Any) -> None:
        raise RuntimeError("boom")

    mw = TracenticMiddleware(
        failing,
        request_attributes=lambda _s: {"request_id": "r-1"},
    )
    with pytest.raises(RuntimeError):
        await mw({"type": "http"}, _noop_receive, _noop_send)

    assert ctx.get_all() == {"service": "api"}


async def test_bypasses_non_http_scopes() -> None:
    calls: list[str] = []

    async def app(scope: Any, receive: Any, send: Any) -> None:
        calls.append(scope["type"])

    mw = TracenticMiddleware(
        app,
        request_attributes=lambda _s: {"should_not": "apply"},
    )
    await mw({"type": "lifespan"}, _noop_receive, _noop_send)

    # Middleware forwarded the scope without touching the context.
    assert calls == ["lifespan"]
    assert "should_not" not in TracenticGlobalContext.current.get_all()


async def test_none_value_suppresses_existing_key() -> None:
    ctx = TracenticGlobalContext.current
    ctx.set("service", "api")

    observed: dict[str, Any] = {}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        observed.update(ctx.get_all())

    mw = TracenticMiddleware(
        app,
        request_attributes=lambda _s: {"service": None, "user_id": "u-1"},
    )
    await mw({"type": "http"}, _noop_receive, _noop_send)

    # `service` was removed for the duration of the request, then restored.
    assert observed == {"user_id": "u-1"}
    assert ctx.get_all() == {"service": "api"}


async def test_empty_attributes_skips_snapshot() -> None:
    ctx = TracenticGlobalContext.current
    ctx.set("service", "api")

    observed: dict[str, Any] = {}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        observed.update(ctx.get_all())

    mw = TracenticMiddleware(app, request_attributes=lambda _s: {})
    await mw({"type": "http"}, _noop_receive, _noop_send)

    assert observed == {"service": "api"}


# ── helpers ──────────────────────────────────────────────────────────────────


async def _noop() -> None:
    return None


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request"}


async def _noop_send(_message: dict[str, Any]) -> None:
    return None
