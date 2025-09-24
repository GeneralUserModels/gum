from __future__ import annotations

from typing import Protocol, Sequence

import mss


class ScreenshotBackend(Protocol):
    """Abstract interface for grabbing screen frames."""

    def __enter__(self) -> "ScreenshotBackend":
        ...

    def __exit__(self, exc_type, exc, tb) -> None:
        ...

    @property
    def monitors(self) -> Sequence[dict]:
        ...

    def grab(self, monitor: dict):
        ...


class MssScreenshotBackend:
    """Minimal wrapper around ``mss.mss`` exposing the backend protocol."""

    def __init__(self, **kwargs) -> None:
        self._kwargs = kwargs
        self._mss: mss.mss | None = None

    def __enter__(self) -> "MssScreenshotBackend":
        self._mss = mss.mss(**self._kwargs)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._mss is not None:
            close = getattr(self._mss, "close", None)
            if callable(close):
                close()
            self._mss = None

    @property
    def monitors(self) -> Sequence[dict]:
        if self._mss is None:
            raise RuntimeError("Screenshot backend not initialised; use as a context manager")
        return self._mss.monitors

    def grab(self, monitor: dict):
        if self._mss is None:
            raise RuntimeError("Screenshot backend not initialised; use as a context manager")
        return self._mss.grab(monitor)
