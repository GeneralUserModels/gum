from __future__ import annotations

from typing import Callable, Protocol

MouseClickHandler = Callable[[float, float, str], None]
MouseScrollHandler = Callable[[float, float, float, float], None]


class MouseBackend(Protocol):
    """Abstract interface for mouse event sources."""

    def start(self, on_click: MouseClickHandler, on_scroll: MouseScrollHandler) -> None:
        """Start delivering events towards the provided callbacks."""

    def stop(self) -> None:
        """Stop delivering mouse events and release any resources."""


class NullMouseBackend:
    """Mouse backend stub that never emits events."""

    def start(self, on_click: MouseClickHandler, on_scroll: MouseScrollHandler) -> None:  # pragma: no cover
        return

    def stop(self) -> None:  # pragma: no cover
        return
