from tracentic._attribute_merger import AttributeMerger
from tracentic._global_context import TracenticGlobalContext
from tracentic._options import AttributeLimits
from tracentic._scope import TracenticScope


class TestAttributeMerger:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def _make_merger(
        self,
        global_attrs: dict | None = None,
        limits: AttributeLimits | None = None,
    ) -> AttributeMerger:
        ctx = TracenticGlobalContext()
        if global_attrs:
            for k, v in global_attrs.items():
                ctx.set(k, v)
        return AttributeMerger(ctx, limits or AttributeLimits())

    def test_empty_merge(self) -> None:
        merger = self._make_merger()
        result = merger.merge(None, None)
        assert result == {}

    def test_three_layer_merge_priority(self) -> None:
        merger = self._make_merger({"key": "global", "only_global": "g"})
        scope = TracenticScope("s", attributes={"key": "scope", "only_scope": "s"})
        span_attrs = {"key": "span", "only_span": "sp"}

        result = merger.merge(scope, span_attrs)

        assert result["key"] == "span"  # span wins
        assert result["only_global"] == "g"
        assert result["only_scope"] == "s"
        assert result["only_span"] == "sp"

    def test_key_truncation(self) -> None:
        merger = self._make_merger(limits=AttributeLimits(max_key_length=5))
        result = merger.merge(None, {"longkey": "value"})
        assert "longk" in result
        assert "longkey" not in result

    def test_string_value_truncation(self) -> None:
        merger = self._make_merger(
            limits=AttributeLimits(max_string_value_length=3)
        )
        result = merger.merge(None, {"k": "abcdef"})
        assert result["k"] == "abc"

    def test_non_string_values_not_truncated(self) -> None:
        merger = self._make_merger(
            limits=AttributeLimits(max_string_value_length=3)
        )
        result = merger.merge(None, {"k": 123456})
        assert result["k"] == 123456

    def test_attribute_count_cap(self) -> None:
        merger = self._make_merger(
            limits=AttributeLimits(max_attribute_count=2)
        )
        result = merger.merge(None, {"a": 1, "b": 2, "c": 3})
        assert len(result) == 2

    def test_returns_new_dict(self) -> None:
        merger = self._make_merger({"g": "val"})
        scope = TracenticScope("s", attributes={"s": "val"})
        span_attrs = {"sp": "val"}

        result = merger.merge(scope, span_attrs)

        assert result is not span_attrs
        assert result is not scope.attributes
