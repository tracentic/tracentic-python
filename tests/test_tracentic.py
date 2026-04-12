from datetime import datetime, timezone

import pytest

from tracentic import (
    ModelPricing,
    Tracentic,
    TracenticGlobalContext,
    TracenticOptions,
    TracenticScope,
    TracenticSpan,
    configure,
    create_tracentic,
    get_tracentic,
)


class TestCreateTracentic:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def test_returns_tracentic_instance(self) -> None:
        t = create_tracentic()
        assert isinstance(t, Tracentic)

    def test_sets_global_context_as_current(self) -> None:
        create_tracentic()
        # Should not raise
        _ = TracenticGlobalContext.current

    def test_applies_global_attributes(self) -> None:
        create_tracentic(
            TracenticOptions(
                global_attributes={"region": "us-east-1", "version": "1.0"}
            )
        )
        assert TracenticGlobalContext.current.get_all() == {
            "region": "us-east-1",
            "version": "1.0",
        }

    def test_works_without_api_key(self) -> None:
        t = create_tracentic(TracenticOptions(service_name="test"))
        scope = t.begin("op")
        # Should not raise even without exporter
        t.record_span(
            scope,
            TracenticSpan(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
            ),
        )


class TestBegin:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def test_creates_root_scope(self) -> None:
        t = create_tracentic()
        scope = t.begin("my-operation")
        assert isinstance(scope, TracenticScope)
        assert scope.name == "my-operation"
        assert scope.parent_id is None

    def test_creates_scope_with_attributes_and_correlation(self) -> None:
        t = create_tracentic()
        scope = t.begin(
            "op",
            attributes={"doc_id": "doc-1"},
            correlation_id="order-123",
        )
        assert scope.attributes["doc_id"] == "doc-1"
        assert scope.correlation_id == "order-123"

    def test_creates_scope_linked_to_parent(self) -> None:
        t = create_tracentic()
        scope = t.begin("downstream", parent_scope_id="external-scope-id")
        assert scope.parent_id == "external-scope-id"

    def test_defensively_copies_attributes(self) -> None:
        t = create_tracentic()
        attrs = {"key": "original"}
        scope = t.begin("op", attributes=attrs)
        attrs["key"] = "mutated"
        assert scope.attributes["key"] == "original"


class TestRecordSpan:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def test_record_with_scope_no_throw(self) -> None:
        t = create_tracentic()
        scope = t.begin("op")
        t.record_span(
            scope,
            TracenticSpan(
                started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                ended_at=datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=500,
                output_tokens=200,
                operation_type="chat",
            ),
        )

    def test_record_without_scope(self) -> None:
        t = create_tracentic()
        t.record_span(
            TracenticSpan(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                provider="openai",
                operation_type="embedding",
            ),
        )


class TestRecordError:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def test_record_error_with_scope(self) -> None:
        t = create_tracentic()
        scope = t.begin("op")
        t.record_error(
            scope,
            TracenticSpan(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
            ),
            RuntimeError("rate limited"),
        )

    def test_record_error_without_scope(self) -> None:
        t = create_tracentic()
        t.record_error(
            TracenticSpan(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
            ),
            TimeoutError("timeout"),
        )


class TestSingletonAPI:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()
        # Reset the module-level singleton
        import tracentic._client as mod
        mod._singleton = None

    def test_get_tracentic_raises_before_configure(self) -> None:
        with pytest.raises(RuntimeError, match="not been configured"):
            get_tracentic()

    def test_configure_and_get_returns_same_instance(self) -> None:
        t = configure(TracenticOptions(service_name="test"))
        assert get_tracentic() is t


class TestCostCalculation:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def test_does_not_throw_with_pricing(self) -> None:
        t = create_tracentic(
            TracenticOptions(
                custom_pricing={
                    "claude-sonnet-4-6": ModelPricing(
                        input_cost_per_million=3.0,
                        output_cost_per_million=15.0,
                    ),
                }
            )
        )
        t.record_span(
            TracenticSpan(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=1000,
                output_tokens=500,
            ),
        )
