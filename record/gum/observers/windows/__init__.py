"""Windows-specific observer implementations (placeholder)."""

from .keyboard import WindowsKeyboardBackend
from .mouse import WindowsMouseBackend
from .screenshots import WindowsScreenshotBackend
from .app_and_browser_logging import (
    WindowsAppAndBrowserInspector,
    check_automation_permission_granted as windows_check_automation_permission_granted,
)

__all__ = [
    "WindowsKeyboardBackend",
    "WindowsMouseBackend",
    "WindowsScreenshotBackend",
    "WindowsAppAndBrowserInspector",
    "windows_check_automation_permission_granted",
]
