# Changelog

All notable changes to the Tracentic Python SDK are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-17

### Added

- `debug` option on `TracenticOptions` for verbose diagnostic logging. When enabled, the SDK sets the `tracentic` logger to `DEBUG` level and attaches a stream handler (if none exists) so messages appear on stderr. Logs span enqueue, batch flush, export success, and shutdown lifecycle events. Warnings and errors are always emitted regardless of this flag.
- `export_timeout_s` option on `TracenticOptions` to configure the per-request timeout for OTLP exports (default: 30 seconds, previously hardcoded to 5 seconds).
- Queue overflow warning when spans are dropped due to a full export queue.
- README sections for debugging, logging, and export timeout configuration.

### Changed

- Default OTLP export timeout increased from 5 seconds to 30 seconds, matching the .NET SDK. This prevents silent span loss in higher-latency environments such as CI runners and serverless cold starts.
- Export exception logging upgraded from `DEBUG` to `WARNING` level so failures are visible without enabling debug mode.
- Exit handler now logs a warning instead of silently swallowing `RuntimeError` when the event loop is unavailable during shutdown.

## [0.2.0] - 2026-04-15

### Added

- `TRACENTIC_SCOPE_HEADER` constant for cross-service scope-ID propagation. Use this in place of the literal `"x-tracentic-scope-id"` string so a typo on either end can't silently break linking.
- `record_span` now accepts span fields as keyword arguments as an alternative to constructing a `TracenticSpan` instance: `tracentic.record_span(scope, started_at=..., ended_at=..., model=...)`. The original `TracenticSpan`-based form is unchanged.
- One-time warning on the `tracentic` logger when a span has token data but no matching `custom_pricing` entry - surfaces missing cost configuration that previously failed silently. Emitted at most once per unique model.
- Informational log when `create_tracentic` / `configure` is called without an `api_key` - clarifies that spans are created locally but not exported.
- README guidance for serverless runtimes (AWS Lambda, Google Cloud Functions) explaining why `atexit` may not fire and how to `await tracentic.shutdown()` from `finally`.

### Changed

- Default `endpoint` is now `https://tracentic.dev` (previously `https://ingest.tracentic.dev`). Any caller passing an explicit `endpoint` is unaffected.
- README clarifies that `custom_pricing` is required for cost tracking - there are no built-in pricing defaults - and that the SDK warns when it's missing.
- README quick start now includes `custom_pricing` and uses the kwargs form of `record_span` so the expected configuration shape is visible by default.

## [0.1.0] - 2026-04-15

Initial public release.

### Added

- Scoped tracing with `Tracentic.begin`, `TracenticScope.create_child`, and cross-service linking via `parent_scope_id`.
- Span recording (`record_span`, `record_error`) with and without a scope.
- Three-layer attribute merge (global < scope < span) with platform-enforced limits.
- Global attribute context (`TracenticGlobalContext`) with static and dynamic attributes.
- Optional Starlette/FastAPI middleware for per-request attribute injection.
- LLM cost calculation from user-supplied `custom_pricing`.
- OTLP/HTTP JSON exporter with batched async delivery, bounded queue, and graceful shutdown flush.
- Python 3.10+ support with `py.typed` marker for full type-checking.

### Fixed

- Exporter no longer leaks an `httpx.AsyncClient` when flushing without a pre-initialised client (e.g. from an `atexit` shutdown).

[Unreleased]: https://github.com/tracentic/tracentic-python/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/tracentic/tracentic-python/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tracentic/tracentic-python/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tracentic/tracentic-python/releases/tag/v0.1.0
