from __future__ import annotations

from typing import Optional


class FallbackAppAndBrowserInspector:  # pragma: no cover - placeholder behaviour
    """Fallback stub used on platforms without UI automation support."""

    def __init__(self, logger) -> None:
        self.logger = logger
        self.last_frontmost_bundle_id: Optional[str] = None

    def get_frontmost_app_name(self) -> Optional[str]:
        return None

    def get_browser_url(self, app_name: Optional[str]) -> Optional[str]:
        return None

    def snapshot_running_browsers(self):  # type: ignore[override]
        return []

    def prime_automation_for_running_browsers(self) -> bool:
        return False


def check_automation_permission_granted(force_refresh: bool = False) -> Optional[bool]:
    """Always returns *None* to indicate unknown automation status."""
    return None


__all__ = ["FallbackAppAndBrowserInspector", "check_automation_permission_granted"]
