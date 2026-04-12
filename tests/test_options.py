from tracentic import AttributeLimits


class TestAttributeLimits:
    def test_defaults_to_platform_maximums(self) -> None:
        limits = AttributeLimits()
        assert limits.max_attribute_count == 128
        assert limits.max_string_value_length == 4096
        assert limits.max_key_length == 256

    def test_accepts_custom_values_within_range(self) -> None:
        limits = AttributeLimits(
            max_attribute_count=50,
            max_string_value_length=1000,
            max_key_length=100,
        )
        assert limits.max_attribute_count == 50
        assert limits.max_string_value_length == 1000
        assert limits.max_key_length == 100

    def test_clamps_to_platform_maximums(self) -> None:
        limits = AttributeLimits(
            max_attribute_count=999,
            max_string_value_length=99999,
            max_key_length=9999,
        )
        assert limits.max_attribute_count == 128
        assert limits.max_string_value_length == 4096
        assert limits.max_key_length == 256

    def test_clamps_minimum_to_one(self) -> None:
        limits = AttributeLimits(
            max_attribute_count=0,
            max_string_value_length=-5,
            max_key_length=0,
        )
        assert limits.max_attribute_count == 1
        assert limits.max_string_value_length == 1
        assert limits.max_key_length == 1

    def test_exposes_platform_constants(self) -> None:
        assert AttributeLimits.PLATFORM_MAX_ATTRIBUTE_COUNT == 128
        assert AttributeLimits.PLATFORM_MAX_STRING_VALUE_LENGTH == 4096
        assert AttributeLimits.PLATFORM_MAX_KEY_LENGTH == 256
