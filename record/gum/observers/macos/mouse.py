from __future__ import annotations

from ..base.mouse import MouseBackend, MouseClickHandler, MouseScrollHandler
from ..fallback.mouse import PynputMouseBackend


class MacMouseBackend(MouseBackend):
    """macOS mouse backend delegating to the shared pynput implementation."""

    def __init__(self) -> None:
        self._delegate = PynputMouseBackend()

    def start(self, on_click: MouseClickHandler, on_scroll: MouseScrollHandler) -> None:
        self._delegate.start(on_click, on_scroll)

    def stop(self) -> None:
        self._delegate.stop()
