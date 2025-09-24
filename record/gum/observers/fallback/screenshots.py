from __future__ import annotations

from ..base.screenshots import MssScreenshotBackend


class FallbackScreenshotBackend(MssScreenshotBackend):
    """Default cross-platform screenshot backend using ``mss``."""

    def __init__(self) -> None:
        super().__init__()
