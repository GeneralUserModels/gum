from __future__ import annotations

from typing import Optional

from pynput import keyboard

from ..base.keyboard import KeyDispatch, KeyboardBackend


def _token_from_key(key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
    try:
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return f"TEXT:{key.char}"
            if key.vk is not None:
                return f"VK:{key.vk}"
        elif isinstance(key, keyboard.Key):
            name = getattr(key, "name", None)
            if name:
                return f"KEY:{name}"
            return f"KEY:{str(key)}"
    except Exception:
        return None
    return None


class PynputKeyboardBackend(KeyboardBackend):
    """Simple keyboard listener that reports events via a callback."""

    def __init__(self) -> None:
        self._listener: Optional[keyboard.Listener] = None
        self._dispatch: Optional[KeyDispatch] = None

    def start(self, dispatch: KeyDispatch) -> None:
        self._dispatch = dispatch
        if self._listener is not None:
            return

        def _emit(event_key, event_type: str) -> None:
            token = _token_from_key(event_key)
            if not token or self._dispatch is None:
                return
            try:
                self._dispatch(token, event_type)
            except Exception:
                pass

        self._listener = keyboard.Listener(
            on_press=lambda key: _emit(key, "press"),
            on_release=lambda key: _emit(key, "release"),
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        finally:
            self._listener = None
            self._dispatch = None
