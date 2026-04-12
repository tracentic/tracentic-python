from tracentic import TracenticScope


class TestTracenticScope:
    def test_generates_32_char_hex_id(self) -> None:
        scope = TracenticScope("test")
        assert len(scope.id) == 32
        int(scope.id, 16)  # should not raise

    def test_defensively_copies_attributes(self) -> None:
        attrs = {"key": "original"}
        scope = TracenticScope("test", attributes=attrs)
        attrs["key"] = "mutated"
        assert scope.attributes["key"] == "original"

    def test_parent_id_is_none_for_root(self) -> None:
        scope = TracenticScope("root")
        assert scope.parent_id is None

    def test_create_child_sets_parent_id(self) -> None:
        parent = TracenticScope("parent")
        child = parent.create_child("child")
        assert child.parent_id == parent.id

    def test_create_child_with_attributes_and_correlation(self) -> None:
        parent = TracenticScope("parent")
        child = parent.create_child(
            "child",
            attributes={"foo": "bar"},
            correlation_id="order-123",
        )
        assert child.attributes["foo"] == "bar"
        assert child.correlation_id == "order-123"
        assert child.parent_id == parent.id

    def test_create_child_defensively_copies_attributes(self) -> None:
        parent = TracenticScope("parent")
        attrs = {"key": "original"}
        child = parent.create_child("child", attributes=attrs)
        attrs["key"] = "mutated"
        assert child.attributes["key"] == "original"

    def test_unique_ids_across_instances(self) -> None:
        ids = {TracenticScope("s").id for _ in range(100)}
        assert len(ids) == 100

    def test_stores_correlation_id(self) -> None:
        scope = TracenticScope("test", correlation_id="corr-456")
        assert scope.correlation_id == "corr-456"

    def test_stores_explicit_parent_id(self) -> None:
        scope = TracenticScope("test", parent_id="external-parent")
        assert scope.parent_id == "external-parent"
