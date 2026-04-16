# Tracentic Python SDK

LLM observability with scoped tracing and OTLP export for Python applications.

## Installation

```bash
pip install tracentic
```

Requires **Python 3.10+**. The only runtime dependency is [httpx](https://www.python-httpx.org/).

## Endpoint

Point the SDK at the Tracentic ingestion endpoint by setting `endpoint="https://tracentic.dev"` on `TracenticOptions`. This is the hosted service URL that receives spans over OTLP/HTTP JSON — use it unless you're running a self-hosted Tracentic deployment, in which case set your own URL.

```python
tracentic = create_tracentic(TracenticOptions(
    api_key="your-api-key",
    endpoint="https://tracentic.dev",
    service_name="my-service",
))
```

## Quick start

```python
import asyncio
from datetime import datetime, timezone
from tracentic import TracenticOptions, TracenticSpan, create_tracentic

from tracentic import ModelPricing

tracentic = create_tracentic(TracenticOptions(
    api_key="your-api-key",
    endpoint="https://tracentic.dev",
    service_name="my-service",
    environment="production",
    # Required for cost tracking. Without this, llm.cost.total_usd is
    # omitted and the SDK warns once per unpriced model.
    custom_pricing={
        "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0),
        "gpt-4o": ModelPricing(2.5, 10.0),
    },
))

async def summarize(text: str) -> str:
    scope = tracentic.begin("summarize", attributes={"user_id": "user-123"})

    started_at = datetime.now(timezone.utc)
    result = await call_llm(text)
    ended_at = datetime.now(timezone.utc)

    # Pass span fields as keyword arguments — no need to construct
    # TracenticSpan manually. (You can still pass a TracenticSpan
    # instance if you prefer.)
    tracentic.record_span(
        scope,
        started_at=started_at,
        ended_at=ended_at,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        operation_type="chat",
    )

    return result.text
```

### Singleton pattern

If you prefer a global instance:

```python
from tracentic import configure, get_tracentic

# At startup
configure(TracenticOptions(api_key="...", service_name="my-service"))

# Anywhere else
tracentic = get_tracentic()
```

## Features

### Scoped tracing

Group related LLM calls under a logical scope. Nest scopes for multi-step pipelines:

```python
pipeline = tracentic.begin("rag-pipeline", correlation_id="order-42")

# Child scope inherits the parent link automatically
synthesis = pipeline.create_child("synthesis", attributes={"strategy": "hybrid"})
```

### Error recording

```python
tracentic.record_error(scope, span, RuntimeError("rate limited"))
```

### Scopeless spans

For standalone LLM calls that don't belong to a larger operation:

```python
tracentic.record_span(TracenticSpan(
    started_at=started_at,
    ended_at=ended_at,
    provider="openai",
    model="gpt-4o-mini",
    input_tokens=200,
    output_tokens=50,
    operation_type="chat",
))
```

### Custom pricing

`custom_pricing` is required for cost tracking. The SDK does not ship with built-in pricing because model prices change frequently and vary by contract. If a span has token data but no matching pricing entry, `llm.cost.total_usd` is omitted and the SDK logs a warning once per model on the `tracentic` logger.

```python
from tracentic import ModelPricing

tracentic = create_tracentic(TracenticOptions(
    api_key="...",
    custom_pricing={
        "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0),
        "gpt-4o": ModelPricing(2.5, 10.0),
    },
))
```

### Global attributes

Pass `global_attributes` to `create_tracentic()` via `TracenticOptions` to tag every span this service emits with the same static values — region, deployment version, owning team, cluster name. They're resolved once at startup and merged into every span without per-call bookkeeping:

```python
tracentic = create_tracentic(TracenticOptions(
    api_key="...",
    service_name="my-service",
    environment="production",
    global_attributes={
        "region": "us-east-1",
        "version": "2.1.0",
        "team": "platform",
    },
))

# Every span this service emits now carries region, version, team.
```

Scope and per-span attributes override global values on key collision, so `global_attributes` is the right layer for defaults you want everywhere unless something more specific says otherwise:

```python
scope = tracentic.begin("request", attributes={"region": "us-west-2"})
# Spans in this scope carry region="us-west-2" (scope wins over global).
```

For values that change after startup — a deploy ID rotated by a background job, a maintenance-mode flag — use `TracenticGlobalContext` to set/remove entries at runtime:

```python
from tracentic import TracenticGlobalContext

TracenticGlobalContext.current.set("deploy_id", "deploy-abc")
# ... spans recorded now include deploy_id ...
TracenticGlobalContext.current.remove("deploy_id")
```

`TracenticGlobalContext` is process-wide (not `contextvars`-based), so values set from one request's handler will leak into every other request running concurrently. For ambient per-request data (user ID, tenant, request ID), use the ASGI middleware below instead.

### ASGI middleware

Inject per-request attributes for the duration of each HTTP request. Works with FastAPI, Starlette, and any ASGI framework:

```python
from tracentic.middleware.asgi import TracenticMiddleware

app = TracenticMiddleware(
    app,
    request_attributes=lambda scope: {
        "method": scope.get("method"),
        "path": scope.get("path"),
    },
)
```

### Cross-service linking

Tracentic does not propagate scope IDs automatically — you pass them explicitly through whatever transport connects your services (HTTP headers, message properties, etc.).

For cross-service linking to work, both services must integrate the Tracentic SDK (or implement the OTLP JSON ingest API directly) and their API keys must belong to the **same tenant**. Spans from different tenants are isolated and cannot be linked.

Use the exported `TRACENTIC_SCOPE_HEADER` constant on both ends rather than a string literal — typos silently break linking.

**Via HTTP header:**

```python
from tracentic import TRACENTIC_SCOPE_HEADER

# Service A — outgoing request
scope = tracentic.begin("gateway-handler")
response = await httpx.post(
    "https://worker.internal/process",
    headers={TRACENTIC_SCOPE_HEADER: scope.id},
)

# Service B — incoming request (FastAPI example)
@app.post("/process")
async def process(request: Request):
    parent_scope_id = request.headers.get(TRACENTIC_SCOPE_HEADER)
    linked = tracentic.begin("worker", parent_scope_id=parent_scope_id)
```

**Via message queue:**

```python
from tracentic import TRACENTIC_SCOPE_HEADER

# Producer
scope = tracentic.begin("order-processor")
await queue.send(
    body=payload,
    properties={TRACENTIC_SCOPE_HEADER: scope.id},
)

# Consumer
async def handle(message):
    parent_scope_id = message.properties[TRACENTIC_SCOPE_HEADER]
    linked = tracentic.begin("fulfillment", parent_scope_id=parent_scope_id)
```

### Shutdown

Buffered spans are flushed automatically at process exit via an `atexit` handler, so you don't need to call `shutdown()` in normal use. Call it explicitly only if you want to flush at a specific point (e.g. before forking or when `atexit` won't run, such as on `os._exit()` or fatal signals):

```python
await tracentic.shutdown()
```

### Serverless (AWS Lambda, Google Cloud Functions)

Serverless runtimes freeze or kill the process between invocations, so the `atexit` handler may never fire and any spans still in the buffer are lost. **Always `await tracentic.shutdown()` before your handler returns:**

```python
async def handler(event, context):
    try:
        return await do_work(event)
    finally:
        # Flush before the runtime freezes the container
        await tracentic.shutdown()
```

Without this, you will see spans appear inconsistently — only when a container happens to be reused and the next invocation triggers a flush.

## Configuration reference

| Option | Default | Description |
|--------|---------|-------------|
| `api_key` | `None` | API key. If `None`, spans are created locally but not exported |
| `service_name` | `"unknown-service"` | Service identifier in the dashboard |
| `endpoint` | `"https://tracentic.dev"` | Tracentic ingestion endpoint. Use `https://tracentic.dev` for the hosted service. Override only for self-hosted deployments. |
| `environment` | `"production"` | Deployment environment tag |
| `custom_pricing` | `None` | Model pricing for cost calculation |
| `global_attributes` | `None` | Static attributes on every span |
| `attribute_limits` | platform defaults | Limits on attribute count, key/value length |

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
# All tests
pytest

# Verbose output
pytest -v

# A single test file
pytest tests/test_scope.py

# A single test
pytest tests/test_scope.py::TestTracenticScope::test_create_child_sets_parent_id
```

### Test files

| File | What it covers |
|------|----------------|
| `test_tracentic.py` | SDK factory, singleton, begin/record_span/record_error, cost calculation |
| `test_scope.py` | Scope creation, nesting, defensive copying, unique IDs |
| `test_global_context.py` | Global context set/get/remove, singleton access, snapshots |
| `test_attribute_merger.py` | Three-layer merge priority, key/value truncation, count cap |
| `test_options.py` | AttributeLimits defaults, clamping, platform constants |
| `test_exporter.py` | OTLP JSON structure, endpoint, headers, overflow, error handling |

### Linting and type checking

```bash
ruff check src/ tests/
mypy src/
```
