"""Merges three layers of attributes with limit enforcement."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._global_context import TracenticGlobalContext
from ._options import AttributeLimits
from ._scope import TracenticScope


class AttributeMerger:
    """Merges three layers of attributes into a single flat dict.

    Priority (lowest -> highest): global -> scope -> span.
    On key collision the higher layer wins.  The merge always produces
    a new dict - no input is mutated.

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
        # Build the result in priority order (span -> scope -> global) so that
        # when max_attribute_count is hit, the lower-priority layers are the
        # ones dropped - never a span-level attribute.
        result: dict[str, Any] = {}

        if span_attributes:
            self._add_layer(result, span_attributes)

        if scope is not None and len(result) < self._limits.max_attribute_count:
            self._add_layer(result, scope.attributes)

        if len(result) < self._limits.max_attribute_count:
            self._add_layer(result, self._global.get_all())

        return result

    def _add_layer(
        self,
        result: dict[str, Any],
        layer: Mapping[str, Any],
    ) -> None:
        for key, value in layer.items():
            safe_key = (
                key[: self._limits.max_key_length]
                if len(key) > self._limits.max_key_length
                else key
            )

            # Higher-priority layer already wrote this key - skip; do not let a
            # lower-priority layer overwrite it.
            if safe_key in result:
                continue

            if len(result) >= self._limits.max_attribute_count:
                return

            safe_value = (
                value[: self._limits.max_string_value_length]
                if isinstance(value, str)
                and len(value) > self._limits.max_string_value_length
                else value
            )

            result[safe_key] = safe_value
