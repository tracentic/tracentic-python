# Changelog

All notable changes to the Tracentic Python SDK are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/tracentic/tracentic-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tracentic/tracentic-python/releases/tag/v0.1.0
