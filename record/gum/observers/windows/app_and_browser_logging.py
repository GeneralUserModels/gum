from __future__ import annotations

from typing import Optional


class WindowsAppAndBrowserInspector:
    """Windows stub for UI automation hooks (not yet implemented)."""

    def __init__(self, logger) -> None:
        self.logger = logger
        self.last_frontmost_bundle_id: Optional[str] = None

    def get_frontmost_app_name(self) -> Optional[str]:
        return None

    def snapshot_running_browsers(self): 
        return []


def check_automation_permission_granted(force_refresh: bool = False) -> Optional[bool]:
    return None


__all__ = ["WindowsAppAndBrowserInspector", "check_automation_permission_granted"]
