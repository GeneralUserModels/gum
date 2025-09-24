from __future__ import annotations

from typing import Optional

from pynput import mouse as pynput_mouse

from ..base.mouse import MouseBackend, MouseClickHandler, MouseScrollHandler


class PynputMouseBackend(MouseBackend):
    """Mouse backend built on ``pynput``'s global listener."""

    def __init__(self) -> None:
        self._listener: Optional[pynput_mouse.Listener] = None

    def start(self, on_click: MouseClickHandler, on_scroll: MouseScrollHandler) -> None:
        if self._listener is not None:
            return

        def handle_click(x, y, button, pressed):
            if not pressed:
                return
            name = getattr(button, "name", str(button))
            on_click(x, y, f"click_{name}")

        self._listener = pynput_mouse.Listener(
            on_click=handle_click,
            on_scroll=lambda x, y, dx, dy: on_scroll(x, y, dx, dy),
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        finally:
            self._listener = None
