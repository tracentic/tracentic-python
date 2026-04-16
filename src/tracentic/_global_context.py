"""Global attributes applied to every span."""

from __future__ import annotations

from typing import Any


class _CurrentDescriptor:
    """Descriptor that makes ``TracenticGlobalContext.current`` behave
    like a class-level property (``@classmethod @property`` was
    deprecated in 3.11 and broken in 3.13)."""

    def __get__(
        self, obj: object, owner: type[TracenticGlobalContext]
    ) -> TracenticGlobalContext:
        if owner._current is None:
            raise RuntimeError(
                "TracenticGlobalContext has not been initialized. "
                "Call create_tracentic() or configure() first."
            )
        return owner._current


class TracenticGlobalContext:
    """Store for global attributes applied to every span.

    Accessible via the :attr:`current` class attribute or passed directly.
    ``get_all()`` returns a snapshot - callers cannot mutate internal state.
    """

    _current: TracenticGlobalContext | None = None

    current: TracenticGlobalContext = _CurrentDescriptor()  # type: ignore[assignment]

    @classmethod
    def _set_current(cls, instance: TracenticGlobalContext) -> None:
        cls._current = instance

    @classmethod
    def _reset_current(cls) -> None:
        cls._current = None

    def __init__(self) -> None:
        self._attributes: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """Set a global attribute."""
        self._attributes[key] = value

    def remove(self, key: str) -> None:
        """Remove a global attribute."""
        self._attributes.pop(key, None)

    def get_all(self) -> dict[str, Any]:
        """Snapshot of all current global attributes."""
        return dict(self._attributes)
