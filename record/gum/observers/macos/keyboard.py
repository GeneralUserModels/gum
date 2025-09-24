from __future__ import annotations

import logging
import os
from typing import List, Optional

try:  # pragma: no cover - AppKit only available on macOS
    from AppKit import (
        NSEvent,
        NSEventMaskKeyDown,
        NSEventMaskKeyUp,
    )
except Exception:  # pragma: no cover - enables import on non-macOS platforms
    NSEvent = None
    NSEventMaskKeyDown = 0
    NSEventMaskKeyUp = 0

try:  # pragma: no cover - optional accessibility check
    import Quartz
except Exception:  # pragma: no cover
    Quartz = None

from ..base.keyboard import KeyDispatch, KeyboardBackend
from ..fallback.keyboard import PynputKeyboardBackend

log = logging.getLogger("Screen.MacKeyboard")


def _token_from_event(event) -> tuple[str, Optional[str]]:
    tok: Optional[str]
    try:
        txt = event.characters() or event.charactersIgnoringModifiers() or ""
    except Exception:
        txt = ""
    try:
        vk: Optional[int] = int(event.keyCode())
    except Exception:
        vk = None

    if txt:
        tok = f"TEXT:{txt}"
    elif vk is not None:
        tok = f"VK:{vk}"
    else:
        tok = "KEY:unknown"
    return tok, txt


def event_token_from_nsevent(event) -> str:
    """Public helper to derive our key token string from an AppKit NSEvent.

    Centralizes token generation so other components (e.g., GUI main-thread shim)
    can reuse identical logic without duplication.
    """
    tok, _ = _token_from_event(event)
    return tok


def register_appkit_key_monitors(on_key_down, on_key_up) -> list[object]:
    """Register global AppKit key down/up monitors and return monitor handles.

    Raises RuntimeError if AppKit is unavailable.
    """
    if NSEvent is None:
        raise RuntimeError("AppKit is not available on this platform")
    monitors: list[object] = [
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_key_down),
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyUp, on_key_up),
    ]
    return monitors


def remove_appkit_monitors(monitors: list[object]) -> None:
    if not monitors or NSEvent is None:
        return
    for monitor in monitors:
        try:
            NSEvent.removeMonitor_(monitor)
        except Exception:
            pass


class AppKitKeyboardBackend(KeyboardBackend):
    """Keyboard backend built on AppKit global event monitoring."""

    def __init__(self) -> None:
        self._monitors: List[object] = []
        self._dispatch: Optional[KeyDispatch] = None

    @staticmethod
    def supported() -> bool:
        return NSEvent is not None

    def start(self, dispatch: KeyDispatch) -> None:
        if NSEvent is None:
            raise RuntimeError("AppKit is not available on this platform")
        if self._monitors:
            return

        self._dispatch = dispatch

        def emit(event, kind: str) -> None:
            if self._dispatch is None:
                return
            try:
                tok, _ = _token_from_event(event)
                if tok:
                    self._dispatch(tok, kind)
            except Exception as exc:
                log.debug(f"Failed to dispatch AppKit {kind} event: {exc}")

        try:
            self._monitors = register_appkit_key_monitors(lambda ev: emit(ev, "press"), lambda ev: emit(ev, "release"))
        except Exception as exc:
            self.stop()
            raise RuntimeError(f"Failed to register AppKit monitors: {exc}") from exc

        log.info("Keyboard monitoring enabled (AppKit)")

    def stop(self) -> None:
        if not self._monitors or NSEvent is None:
            self._monitors = []
            return
        try:
            remove_appkit_monitors(self._monitors)
        finally:
            self._monitors = []
            self._dispatch = None


class MacKeyboardBackend(KeyboardBackend):
    """macOS keyboard backend that prefers AppKit but falls back to pynput."""

    def __init__(self) -> None:
        self._appkit = AppKitKeyboardBackend() if AppKitKeyboardBackend.supported() else None
        self._pynput = PynputKeyboardBackend()
        self._active: KeyboardBackend | None = None

    @staticmethod
    def _has_appkit_access() -> bool:
        if Quartz is None:
            return False
        try:
            mask_fn = getattr(Quartz, "CGEventMaskBit", None)
            if mask_fn is None:
                return False
            mask = mask_fn(Quartz.kCGEventKeyDown) | mask_fn(Quartz.kCGEventKeyUp)
            return bool(Quartz.CGPreflightListenEventAccess(mask))
        except Exception:
            return False

    def start(self, dispatch: KeyDispatch) -> None:
        prefer_raw = os.environ.get("GUM_KEYBOARD_BACKEND", "auto")
        prefer = (prefer_raw or "auto").strip().lower()
        if prefer not in {"auto", "appkit", "pynput"}:
            prefer = "auto"

        attempted_appkit = False
        if self._appkit is not None and prefer != "pynput":
            attempted_appkit = True
            has_access = self._has_appkit_access()
            if not has_access and prefer == "auto":
                log.debug(
                    "AppKit keyboard backend preflight denied accessibility permission; using pynput instead"
                )
            else:
                if not has_access:
                    log.warning(
                        "AppKit keyboard backend requested without accessibility permission; attempting anyway"
                    )
                try:
                    self._appkit.start(dispatch)
                except Exception as exc:
                    log.warning(f"AppKit keyboard backend unavailable, falling back to pynput: {exc}")
                    self._appkit.stop()
                else:
                    self._active = self._appkit
                    return

        if prefer == "appkit":
            log.warning("AppKit keyboard backend requested but unavailable; using pynput fallback")
        elif prefer == "pynput":
            log.info("Keyboard monitoring forced to pynput backend")

        self._pynput.start(dispatch)
        self._active = self._pynput
        if attempted_appkit and prefer != "pynput":
            log.info("Keyboard monitoring enabled (pynput fallback)")
        else:
            log.info("Keyboard monitoring enabled (pynput)")

    def stop(self) -> None:
        try:
            if self._active is not None:
                self._active.stop()
        finally:
            self._active = None
