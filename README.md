# Tracentic Python SDK

LLM observability with scoped tracing and OTLP export for Python applications.

## Installation

```bash
pip install tracentic
```

Requires **Python 3.10+**. The only runtime dependency is [httpx](https://www.python-httpx.org/).

## Quick start

```python
import asyncio
from datetime import datetime, timezone
from tracentic import TracenticOptions, TracenticSpan, create_tracentic

tracentic = create_tracentic(TracenticOptions(
    api_key="your-api-key",
    service_name="my-service",
    environment="production",
))

async def summarize(text: str) -> str:
    scope = tracentic.begin("summarize", attributes={"user_id": "user-123"})

    started_at = datetime.now(timezone.utc)
    result = await call_llm(text)
    ended_at = datetime.now(timezone.utc)

    tracentic.record_span(scope, TracenticSpan(
        started_at=started_at,
        ended_at=ended_at,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        operation_type="chat",
    ))

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

Cost is calculated automatically when a matching pricing entry exists and both token counts are present.

### Global attributes

Static attributes applied to every span:

```python
tracentic = create_tracentic(TracenticOptions(
    api_key="...",
    global_attributes={
        "region": "us-east-1",
        "version": "2.1.0",
    },
))
```

Dynamic attributes can be set/removed at runtime:

```python
from tracentic import TracenticGlobalContext

TracenticGlobalContext.current.set("deploy_id", "deploy-abc")
TracenticGlobalContext.current.remove("deploy_id")
```

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

**Via HTTP header:**

```python
# Service A — outgoing request
scope = tracentic.begin("gateway-handler")
response = await httpx.post(
    "https://worker.internal/process",
    headers={"x-tracentic-scope-id": scope.id},
)

# Service B — incoming request (FastAPI example)
@app.post("/process")
async def process(request: Request):
    parent_scope_id = request.headers.get("x-tracentic-scope-id")
    linked = tracentic.begin("worker", parent_scope_id=parent_scope_id)
```

**Via message queue:**

```python
# Producer
scope = tracentic.begin("order-processor")
await queue.send(
    body=payload,
    properties={"tracentic-scope-id": scope.id},
)

# Consumer
async def handle(message):
    parent_scope_id = message.properties["tracentic-scope-id"]
    linked = tracentic.begin("fulfillment", parent_scope_id=parent_scope_id)
```

### Shutdown

Flush buffered spans before process exit:

```python
await tracentic.shutdown()
```

## Configuration reference

| Option | Default | Description |
|--------|---------|-------------|
| `api_key` | `None` | API key. If `None`, spans are created locally but not exported |
| `service_name` | `"unknown-service"` | Service identifier in the dashboard |
| `endpoint` | `"https://ingest.tracentic.dev"` | OTLP ingestion endpoint |
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
