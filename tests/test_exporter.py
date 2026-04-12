import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from tracentic._exporter import ExportableSpan, OtlpJsonExporter


def _make_span(**overrides: object) -> ExportableSpan:
    defaults = {
        "name": "llm.anthropic.chat",
        "started_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "ended_at": datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        "attributes": {"llm.provider": "anthropic"},
        "status": "ok",
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return ExportableSpan(**defaults)  # type: ignore[arg-type]


class TestOtlpJsonExporter:
    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_to_correct_endpoint(self) -> None:
        route = respx.post("https://ingest.tracentic.dev/v1/ingest").respond(200)

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="test-key",
            service_name="test-service",
            environment="test",
        )
        exporter.enqueue(_make_span())
        await exporter.shutdown()

        assert route.called
        request = route.calls[0].request
        assert request.headers["content-type"] == "application/json"
        assert request.headers["x-tracentic-api-key"] == "test-key"

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_valid_otlp_structure(self) -> None:
        route = respx.post("https://ingest.tracentic.dev/v1/ingest").respond(200)

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="key",
            service_name="svc",
            environment="prod",
        )
        exporter.enqueue(_make_span())
        await exporter.shutdown()

        body = json.loads(route.calls[0].request.content)
        assert len(body["resourceSpans"]) == 1

        rs = body["resourceSpans"][0]
        assert rs["resource"]["attributes"] is not None
        assert len(rs["scopeSpans"]) == 1

        ss = rs["scopeSpans"][0]
        assert ss["scope"]["name"] == "Tracentic"
        assert len(ss["spans"]) == 1

        span = ss["spans"][0]
        assert span["name"] == "llm.anthropic.chat"
        assert span["kind"] == 3  # CLIENT
        assert span["traceId"]
        assert span["spanId"]
        assert span["status"]["code"] == 1  # OK

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_status(self) -> None:
        route = respx.post("https://ingest.tracentic.dev/v1/ingest").respond(200)

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="key",
            service_name="svc",
            environment="prod",
        )
        exporter.enqueue(_make_span(status="error", error_message="rate limited"))
        await exporter.shutdown()

        body = json.loads(route.calls[0].request.content)
        span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["status"]["code"] == 2  # ERROR
        assert span["status"]["message"] == "rate limited"

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_request_when_empty(self) -> None:
        route = respx.post("https://ingest.tracentic.dev/v1/ingest").respond(200)

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="key",
            service_name="svc",
            environment="prod",
        )
        await exporter.shutdown()
        assert not route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_drops_oldest_on_overflow(self) -> None:
        route = respx.post("https://ingest.tracentic.dev/v1/ingest").respond(200)

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="key",
            service_name="svc",
            environment="prod",
        )

        for i in range(513):
            exporter.enqueue(_make_span(name=f"span-{i}"))

        await exporter.shutdown()

        total_spans = 0
        for call in route.calls:
            body = json.loads(call.request.content)
            total_spans += len(body["resourceSpans"][0]["scopeSpans"][0]["spans"])
        assert total_spans <= 512

    @respx.mock
    @pytest.mark.asyncio
    async def test_silently_ignores_failures(self) -> None:
        respx.post("https://ingest.tracentic.dev/v1/ingest").mock(
            side_effect=httpx.ConnectError("network error")
        )

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="key",
            service_name="svc",
            environment="prod",
        )
        exporter.enqueue(_make_span())
        await exporter.shutdown()  # should not raise

    @respx.mock
    @pytest.mark.asyncio
    async def test_includes_resource_attributes(self) -> None:
        route = respx.post("https://ingest.tracentic.dev/v1/ingest").respond(200)

        exporter = OtlpJsonExporter(
            endpoint="https://ingest.tracentic.dev",
            api_key="key",
            service_name="my-service",
            environment="staging",
        )
        exporter.enqueue(_make_span())
        await exporter.shutdown()

        body = json.loads(route.calls[0].request.content)
        resource_attrs = body["resourceSpans"][0]["resource"]["attributes"]
        keys = [a["key"] for a in resource_attrs]
        assert "service.name" in keys
        assert "deployment.environment" in keys
