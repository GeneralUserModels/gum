from __future__ import annotations

from typing import Callable, Protocol

KeyDispatch = Callable[[str, str], None]


class KeyboardBackend(Protocol):
    """Abstract interface for keyboard event backends."""

    def start(self, dispatch: KeyDispatch) -> None:
        """Begin emitting keyboard events via *dispatch* (token, action)."""

    def stop(self) -> None:
        """Stop emitting keyboard events and release any resources."""


class NullKeyboardBackend:
    """Keyboard backend stub that never emits events."""

    def start(self, dispatch: KeyDispatch) -> None:  # pragma: no cover - no behaviour to test
        return

    def stop(self) -> None:  # pragma: no cover - no behaviour to test
        return
