"""OTLP JSON exporter with batched async export."""

from __future__ import annotations

import asyncio
import logging
import os
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

_log = logging.getLogger("tracentic")

_SDK_VERSION = "0.1.0"

_SCHEDULED_DELAY_S = 5.0
_MAX_QUEUE_SIZE = 512
_MAX_BATCH_SIZE = 128


@dataclass(slots=True)
class ExportableSpan:
    """Internal span representation queued for export."""

    name: str
    started_at: datetime
    ended_at: datetime
    attributes: dict[str, Any]
    status: str  # "ok" | "error"
    error_message: str | None = None


class OtlpJsonExporter:
    """Batched OTLP JSON exporter.

    Spans are enqueued and periodically flushed to the ingestion
    endpoint via HTTP POST.  Export failures are logged at WARNING
    level and do not raise exceptions (fire-and-forget).
    """

    __slots__ = (
        "_endpoint",
        "_api_key",
        "_service_name",
        "_environment",
        "_export_timeout_s",
        "_queue",
        "_task",
        "_shutdown_event",
        "_client",
    )

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        service_name: str,
        environment: str,
        export_timeout_s: float = 30.0,
    ) -> None:
        self._endpoint = f"{endpoint.rstrip('/')}/v1/ingest"
        self._api_key = api_key
        self._service_name = service_name
        self._environment = environment
        self._export_timeout_s = export_timeout_s
        self._queue: list[ExportableSpan] = []
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._client: httpx.AsyncClient | None = None

    def _ensure_started(self) -> None:
        """Lazily start the background flush loop on the current event loop."""
        if self._task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - spans will be flushed on shutdown()
            return
        self._shutdown_event = asyncio.Event()
        self._client = httpx.AsyncClient(timeout=self._export_timeout_s)
        self._task = loop.create_task(self._run())

    def enqueue(self, span: ExportableSpan) -> None:
        """Add a span to the export queue."""
        if len(self._queue) >= _MAX_QUEUE_SIZE:
            _log.warning(
                "Tracentic export queue full (%d) - dropping oldest span",
                _MAX_QUEUE_SIZE,
            )
            self._queue.pop(0)
        self._queue.append(span)
        _log.debug(
            "enqueued span %r (queue: %d)", span.name, len(self._queue)
        )
        self._ensure_started()

    async def shutdown(self) -> None:
        """Flush all remaining spans and stop the background task."""
        _log.debug("shutting down exporter...")
        if self._shutdown_event is not None:
            self._shutdown_event.set()
        if self._task is not None:
            await self._task
            self._task = None
        await self._flush()
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        _log.debug("exporter shutdown complete")

    # ── Internal ─────────────────────────────────────────────────

    async def _run(self) -> None:
        assert self._shutdown_event is not None
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=_SCHEDULED_DELAY_S,
                )
            except asyncio.TimeoutError:
                pass
            await self._flush()

    async def _flush(self) -> None:
        if not self._queue:
            return

        batch = self._queue[: _MAX_BATCH_SIZE]
        del self._queue[: _MAX_BATCH_SIZE]
        _log.debug("flushing %d span(s) to %s", len(batch), self._endpoint)

        otlp_spans = [self._convert_span(s) for s in batch]
        request_body = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            _attr("service.name", self._service_name),
                            _attr("service.version", _SDK_VERSION),
                            _attr("deployment.environment", self._environment),
                        ],
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "Tracentic", "version": _SDK_VERSION},
                            "spans": otlp_spans,
                        }
                    ],
                }
            ]
        }

        async def _post(client: httpx.AsyncClient) -> None:
            response = await client.post(
                self._endpoint,
                json=request_body,
                headers={
                    "content-type": "application/json",
                    "x-tracentic-api-key": self._api_key,
                },
            )
            if not response.is_success:
                _log.warning(
                    "Tracentic export failed: %d %s - %s",
                    response.status_code,
                    response.reason_phrase,
                    response.text,
                )
            else:
                _log.debug(
                    "export succeeded: %d (%d spans)",
                    response.status_code,
                    len(batch),
                )

        try:
            if self._client is not None:
                await _post(self._client)
            else:
                async with httpx.AsyncClient(timeout=self._export_timeout_s) as client:
                    await _post(client)
        except Exception as exc:
            _log.warning("Tracentic export error: %s", exc)

        # If there are still items in the queue, flush again
        if self._queue:
            await self._flush()

    @staticmethod
    def _convert_span(span: ExportableSpan) -> dict[str, Any]:
        trace_id = b64encode(os.urandom(16)).decode("ascii")
        span_id = b64encode(os.urandom(8)).decode("ascii")

        start_nano = str(int(span.started_at.timestamp() * 1_000_000_000))
        end_nano = str(int(span.ended_at.timestamp() * 1_000_000_000))

        attributes = [_attr(k, v) for k, v in span.attributes.items()]

        result: dict[str, Any] = {
            "traceId": trace_id,
            "spanId": span_id,
            "name": span.name,
            "kind": 3,  # CLIENT
            "startTimeUnixNano": start_nano,
            "endTimeUnixNano": end_nano,
            "status": {
                "code": 2 if span.status == "error" else 1,
            },
        }

        if attributes:
            result["attributes"] = attributes

        if span.error_message is not None:
            result["status"]["message"] = span.error_message

        return result


def _attr(key: str, value: Any) -> dict[str, Any]:
    """Convert a key-value pair to an OTLP attribute."""
    if isinstance(value, str):
        return {"key": key, "value": {"stringValue": value}}
    if isinstance(value, bool):
        # Check bool before int - bool is a subclass of int in Python
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}
