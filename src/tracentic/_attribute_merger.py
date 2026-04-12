"""Merges three layers of attributes with limit enforcement."""

from __future__ import annotations

from typing import Any

from ._global_context import TracenticGlobalContext
from ._options import AttributeLimits
from ._scope import TracenticScope


class AttributeMerger:
    """Merges three layers of attributes into a single flat dict.

    Priority (lowest -> highest): global -> scope -> span.
    On key collision the higher layer wins.  The merge always produces
    a new dict — no input is mutated.

    Enforces :class:`AttributeLimits` to prevent oversized payloads:
    keys and string values are truncated, and the total attribute count
    is capped.
    """

    __slots__ = ("_global", "_limits")

    def __init__(
        self,
        global_context: TracenticGlobalContext,
        limits: AttributeLimits,
    ) -> None:
        self._global = global_context
        self._limits = limits

    def merge(
        self,
        scope: TracenticScope | None,
        span_attributes: dict[str, Any] | None,
    ) -> dict[str, Any]:
        # Layer 1 — global (lowest priority)
        result: dict[str, Any] = self._global.get_all()

        # Layer 2 — scope attributes
        if scope is not None:
            result.update(scope.attributes)

        # Layer 3 — span-level (highest priority)
        if span_attributes:
            result.update(span_attributes)

        return self._enforce(result)

    def _enforce(self, attrs: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        count = 0

        for key, value in attrs.items():
            safe_key = (
                key[: self._limits.max_key_length]
                if len(key) > self._limits.max_key_length
                else key
            )
            safe_value = (
                value[: self._limits.max_string_value_length]
                if isinstance(value, str)
                and len(value) > self._limits.max_string_value_length
                else value
            )

            result[safe_key] = safe_value
            count += 1

            if count >= self._limits.max_attribute_count:
                break

        return result
