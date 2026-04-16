"""Configuration types for the Tracentic SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_PLATFORM_MAX_ATTRIBUTE_COUNT = 128
_PLATFORM_MAX_STRING_VALUE_LENGTH = 4096
_PLATFORM_MAX_KEY_LENGTH = 256


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Pricing entry for a single model."""

    input_cost_per_million: float
    output_cost_per_million: float


class AttributeLimits:
    """Guards against unbounded attribute data.

    Users may lower these limits to catch accidental bloat during
    development, but values are clamped to platform maximums.
    """

    PLATFORM_MAX_ATTRIBUTE_COUNT: int = _PLATFORM_MAX_ATTRIBUTE_COUNT
    PLATFORM_MAX_STRING_VALUE_LENGTH: int = _PLATFORM_MAX_STRING_VALUE_LENGTH
    PLATFORM_MAX_KEY_LENGTH: int = _PLATFORM_MAX_KEY_LENGTH

    __slots__ = ("max_attribute_count",
                 "max_string_value_length", "max_key_length")

    def __init__(
        self,
        max_attribute_count: int = _PLATFORM_MAX_ATTRIBUTE_COUNT,
        max_string_value_length: int = _PLATFORM_MAX_STRING_VALUE_LENGTH,
        max_key_length: int = _PLATFORM_MAX_KEY_LENGTH,
    ) -> None:
        self.max_attribute_count = _clamp(
            max_attribute_count, 1, _PLATFORM_MAX_ATTRIBUTE_COUNT
        )
        self.max_string_value_length = _clamp(
            max_string_value_length, 1, _PLATFORM_MAX_STRING_VALUE_LENGTH
        )
        self.max_key_length = _clamp(
            max_key_length, 1, _PLATFORM_MAX_KEY_LENGTH)


@dataclass(slots=True)
class TracenticOptions:
    """Configuration options for the Tracentic SDK.

    Attributes:
        api_key: Your Tracentic API key. If ``None``, spans are created
            locally but not exported - enables local dev without an account.
        service_name: Identifies your service in the dashboard.
        endpoint: OTLP ingestion endpoint. Defaults to Tracentic cloud.
        environment: Deployment environment tag.
        custom_pricing: Pricing for LLM cost calculation keyed by model
            identifier (exact, case-sensitive match).
        global_attributes: Static attributes applied to every span for the
            lifetime of the application.
        attribute_limits: Limits applied to user-supplied attributes.
    """

    api_key: str | None = None
    service_name: str = "unknown-service"
    endpoint: str = "https://tracentic.dev"
    environment: str = "production"
    custom_pricing: dict[str, ModelPricing] | None = None
    global_attributes: dict[str, Any] | None = None
    attribute_limits: AttributeLimits = field(default_factory=AttributeLimits)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
