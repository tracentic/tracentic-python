"""Tracentic SDK client — the main entry point."""

from __future__ import annotations

import asyncio
import atexit
from typing import Any, overload

from ._attribute_merger import AttributeMerger
from ._exporter import ExportableSpan, OtlpJsonExporter
from ._global_context import TracenticGlobalContext
from ._options import AttributeLimits, TracenticOptions
from ._scope import TracenticScope
from ._span import TracenticSpan


class Tracentic:
    """Tracentic SDK client.

    Use :func:`create_tracentic` or :func:`configure` to obtain an
    instance rather than constructing directly.
    """

    __slots__ = ("_global", "_merger", "_options", "_exporter", "_exit_registered")

    def __init__(
        self,
        global_context: TracenticGlobalContext,
        *,
        service_name: str,
        endpoint: str,
        environment: str,
        custom_pricing: dict[str, Any] | None,
        attribute_limits: AttributeLimits,
        exporter: OtlpJsonExporter | None,
    ) -> None:
        self._global = global_context
        self._options = {
            "service_name": service_name,
            "endpoint": endpoint,
            "environment": environment,
            "custom_pricing": custom_pricing,
            "attribute_limits": attribute_limits,
        }
        self._merger = AttributeMerger(global_context, attribute_limits)
        self._exporter = exporter
        self._exit_registered = False

        if self._exporter is not None:
            self._register_exit_handler()

    # ── Public API ───────────────────────────────────────────────

    def begin(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        parent_scope_id: str | None = None,
    ) -> TracenticScope:
        """Create a new operation scope."""
        return TracenticScope(
            name,
            attributes=dict(attributes) if attributes else None,
            correlation_id=correlation_id,
            parent_id=parent_scope_id,
        )

    @overload
    def record_span(self, scope: TracenticScope, span: TracenticSpan) -> None: ...
    @overload
    def record_span(self, span: TracenticSpan) -> None: ...

    def record_span(
        self,
        scope_or_span: TracenticScope | TracenticSpan,
        span: TracenticSpan | None = None,
    ) -> None:
        """Record a completed LLM span, optionally associated with a scope."""
        if isinstance(scope_or_span, TracenticScope):
            if span is None:
                raise TypeError(
                    "record_span(scope, span): span argument is required when "
                    "the first argument is a TracenticScope"
                )
            merged = self._merger.merge(scope_or_span, span.attributes)
            self._record_internal(span, merged, scope_or_span)
        else:
            merged = self._merger.merge(None, scope_or_span.attributes)
            self._record_internal(scope_or_span, merged, None)

    @overload
    def record_error(
        self, scope: TracenticScope, span: TracenticSpan, error: BaseException
    ) -> None: ...
    @overload
    def record_error(self, span: TracenticSpan, error: BaseException) -> None: ...

    def record_error(
        self,
        scope_or_span: TracenticScope | TracenticSpan,
        span_or_error: TracenticSpan | BaseException,
        error: BaseException | None = None,
    ) -> None:
        """Record an LLM span that resulted in an error."""
        if isinstance(scope_or_span, TracenticScope):
            if not isinstance(span_or_error, TracenticSpan) or error is None:
                raise TypeError(
                    "record_error(scope, span, error): expected (TracenticScope, "
                    "TracenticSpan, BaseException)"
                )
            merged = self._merger.merge(scope_or_span, span_or_error.attributes)
            self._record_error_internal(span_or_error, merged, error, scope_or_span)
        else:
            if not isinstance(span_or_error, BaseException):
                raise TypeError(
                    "record_error(span, error): second argument must be a "
                    "BaseException"
                )
            merged = self._merger.merge(None, scope_or_span.attributes)
            self._record_error_internal(scope_or_span, merged, span_or_error, None)

    async def shutdown(self) -> None:
        """Flush all buffered spans and shut down the exporter."""
        if self._exporter is not None:
            await self._exporter.shutdown()

    # ── Internal ─────────────────────────────────────────────────

    def _record_internal(
        self,
        span: TracenticSpan,
        merged: dict[str, Any],
        scope: TracenticScope | None,
    ) -> None:
        attrs = dict(merged)
        self._set_llm_attributes(attrs, span)
        self._set_scope_attributes(attrs, scope)
        self._set_cost(attrs, span)

        exportable = ExportableSpan(
            name=_build_span_name(span.provider, span.operation_type),
            started_at=span.started_at,
            ended_at=span.ended_at,
            attributes=attrs,
            status="ok",
        )

        if self._exporter is not None:
            self._exporter.enqueue(exportable)

    def _record_error_internal(
        self,
        span: TracenticSpan,
        merged: dict[str, Any],
        error: BaseException,
        scope: TracenticScope | None,
    ) -> None:
        attrs = dict(merged)
        self._set_llm_attributes(attrs, span)
        self._set_scope_attributes(attrs, scope)
        attrs["llm.error.type"] = type(error).__name__

        exportable = ExportableSpan(
            name=_build_span_name(span.provider, span.operation_type),
            started_at=span.started_at,
            ended_at=span.ended_at,
            attributes=attrs,
            status="error",
            error_message=str(error),
        )

        if self._exporter is not None:
            self._exporter.enqueue(exportable)

    @staticmethod
    def _set_llm_attributes(attrs: dict[str, Any], span: TracenticSpan) -> None:
        if span.provider is not None:
            attrs["llm.provider"] = span.provider
        if span.model is not None:
            attrs["llm.request.model"] = span.model
        if span.operation_type is not None:
            attrs["llm.request.type"] = span.operation_type
        if span.input_tokens is not None:
            attrs["llm.usage.input_tokens"] = span.input_tokens
        if span.output_tokens is not None:
            attrs["llm.usage.output_tokens"] = span.output_tokens
        if span.input_tokens is not None and span.output_tokens is not None:
            attrs["llm.usage.total_tokens"] = span.input_tokens + span.output_tokens

        duration_ms = round(
            (span.ended_at.timestamp() - span.started_at.timestamp()) * 1000
        )
        attrs["llm.duration_ms"] = duration_ms

    @staticmethod
    def _set_scope_attributes(
        attrs: dict[str, Any], scope: TracenticScope | None
    ) -> None:
        if scope is None:
            return
        attrs["tracentic.scope.id"] = scope.id
        attrs["tracentic.scope.name"] = scope.name
        attrs["tracentic.scope.started_at"] = scope.started_at.isoformat()
        if scope.parent_id is not None:
            attrs["tracentic.scope.parent_id"] = scope.parent_id
        if scope.correlation_id is not None:
            attrs["tracentic.scope.correlation_id"] = scope.correlation_id

    def _set_cost(self, attrs: dict[str, Any], span: TracenticSpan) -> None:
        custom_pricing = self._options["custom_pricing"]
        if (
            span.model is None
            or span.input_tokens is None
            or span.output_tokens is None
            or custom_pricing is None
        ):
            return

        pricing = custom_pricing.get(span.model)
        if pricing is None:
            return

        cost = (
            (span.input_tokens / 1_000_000) * pricing.input_cost_per_million
            + (span.output_tokens / 1_000_000) * pricing.output_cost_per_million
        )
        attrs["llm.cost.total_usd"] = cost

    def _register_exit_handler(self) -> None:
        if self._exit_registered:
            return
        self._exit_registered = True

        def _flush_on_exit() -> None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.shutdown())
                else:
                    loop.run_until_complete(self.shutdown())
            except RuntimeError:
                pass

        atexit.register(_flush_on_exit)


def _build_span_name(
    provider: str | None, operation_type: str | None
) -> str:
    if provider and operation_type:
        return f"llm.{provider}.{operation_type}"
    if provider:
        return f"llm.{provider}"
    return "llm.call"


# ── Factory / singleton ──────────────────────────────────────────


def create_tracentic(options: TracenticOptions | None = None) -> Tracentic:
    """Create a new Tracentic SDK instance. This is the primary entry point.

    Example::

        from tracentic import create_tracentic

        tracentic = create_tracentic(TracenticOptions(
            api_key="...",
            service_name="my-service",
        ))
    """
    opts = options or TracenticOptions()

    global_context = TracenticGlobalContext()
    TracenticGlobalContext._set_current(global_context)

    if opts.global_attributes:
        for key, value in opts.global_attributes.items():
            global_context.set(key, value)

    exporter: OtlpJsonExporter | None = None
    if opts.api_key:
        exporter = OtlpJsonExporter(
            endpoint=opts.endpoint,
            api_key=opts.api_key,
            service_name=opts.service_name,
            environment=opts.environment,
        )

    return Tracentic(
        global_context,
        service_name=opts.service_name,
        endpoint=opts.endpoint,
        environment=opts.environment,
        custom_pricing=dict(opts.custom_pricing) if opts.custom_pricing else None,
        attribute_limits=opts.attribute_limits,
        exporter=exporter,
    )


_singleton: Tracentic | None = None


def configure(options: TracenticOptions) -> Tracentic:
    """Configure the global Tracentic singleton. Call once at startup."""
    global _singleton
    _singleton = create_tracentic(options)
    return _singleton


def get_tracentic() -> Tracentic:
    """Return the global Tracentic singleton.

    Raises :class:`RuntimeError` if :func:`configure` has not been called.
    """
    if _singleton is None:
        raise RuntimeError(
            "Tracentic has not been configured. Call configure() first."
        )
    return _singleton
