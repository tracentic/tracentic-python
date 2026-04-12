import pytest

from tracentic import TracenticGlobalContext


class TestTracenticGlobalContext:
    def setup_method(self) -> None:
        TracenticGlobalContext._reset_current()

    def test_set_and_get_all(self) -> None:
        ctx = TracenticGlobalContext()
        ctx.set("region", "us-east-1")
        ctx.set("version", "1.0")
        assert ctx.get_all() == {"region": "us-east-1", "version": "1.0"}

    def test_remove(self) -> None:
        ctx = TracenticGlobalContext()
        ctx.set("key", "value")
        ctx.remove("key")
        assert ctx.get_all() == {}

    def test_remove_nonexistent_key_is_noop(self) -> None:
        ctx = TracenticGlobalContext()
        ctx.remove("nope")  # should not raise

    def test_get_all_returns_snapshot(self) -> None:
        ctx = TracenticGlobalContext()
        ctx.set("key", "value")
        snapshot = ctx.get_all()
        ctx.set("key", "changed")
        assert snapshot["key"] == "value"

    def test_current_raises_before_init(self) -> None:
        with pytest.raises(RuntimeError, match="not been initialized"):
            _ = TracenticGlobalContext.current

    def test_set_current_and_access(self) -> None:
        ctx = TracenticGlobalContext()
        TracenticGlobalContext._set_current(ctx)
        assert TracenticGlobalContext.current is ctx

    def test_reset_current(self) -> None:
        ctx = TracenticGlobalContext()
        TracenticGlobalContext._set_current(ctx)
        TracenticGlobalContext._reset_current()
        with pytest.raises(RuntimeError):
            _ = TracenticGlobalContext.current
