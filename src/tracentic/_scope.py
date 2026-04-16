"""Logical operation scope for grouping related LLM spans."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from uuid import uuid4


class TracenticScope:
    """Represents a logical operation scope.

    Pass to :meth:`~Tracentic.record_span` to associate spans with this
    operation.  Fire-and-forget - no disposal or end call required.

    Create a root scope::

        scope = tracentic.begin("name")

    Create a nested scope::

        child = scope.create_child("name")
    """

    __slots__ = (
        "_id", "_name", "_parent_id", "_correlation_id",
        "_started_at", "_attributes",
    )

    def __init__(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        parent_id: str | None = None,
    ) -> None:
        self._id = uuid4().hex
        self._name = name
        self._parent_id = parent_id
        self._correlation_id = correlation_id
        self._started_at = datetime.now(timezone.utc)
        self._attributes: dict[str, Any] = dict(
            attributes) if attributes else {}

    # ── Read-only properties ─────────────────────────────────────

    @property
    def id(self) -> str:
        """Auto-generated 32-char hex UUID. Always unique."""
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent_id(self) -> str | None:
        return self._parent_id

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @property
    def attributes(self) -> Mapping[str, Any]:
        # Read-only view: callers must not mutate scope state after creation.
        # Returning the raw dict allowed `scope.attributes["x"] = ...` to leak
        # into recorded spans, breaking the "fire and forget" contract.
        return MappingProxyType(self._attributes)

    # ── Child scope creation ─────────────────────────────────────

    def create_child(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> TracenticScope:
        """Creates a child scope nested under this scope.

        The child's ``parent_id`` is set to this scope's ``id``
        automatically.
        """
        return TracenticScope(
            name,
            attributes=dict(attributes) if attributes else None,
            correlation_id=correlation_id,
            parent_id=self._id,
        )
