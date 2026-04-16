"""Data about a single LLM call."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TracenticSpan:
    """Data about a single LLM call.

    Pass to :meth:`~Tracentic.record_span` after the call completes.
    ``started_at`` and ``ended_at`` are required; all other fields are
    optional.
    """

    started_at: datetime
    """UTC timestamp when the LLM call started."""

    ended_at: datetime
    """UTC timestamp when the LLM call completed."""

    provider: str | None = None
    """``"anthropic"``, ``"openai"``, ``"google"``, etc."""

    model: str | None = None
    """The model identifier used for this call."""

    input_tokens: int | None = None
    """Number of input/prompt tokens consumed."""

    output_tokens: int | None = None
    """Number of output/completion tokens generated."""

    operation_type: str | None = None
    """``"chat"``, ``"completion"``, ``"embedding"``"""

    attributes: dict[str, Any] = field(default_factory=dict)
    """Call-specific attributes. Highest merge priority - overrides
    scope and global attributes on key collision."""
