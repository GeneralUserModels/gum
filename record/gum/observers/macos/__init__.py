"""macOS-specific observer implementations."""

from .keyboard import AppKitKeyboardBackend, MacKeyboardBackend
from .mouse import MacMouseBackend
from .screenshots import MacScreenshotBackend, is_app_visible
from .app_and_browser_logging import MacOSAppAndBrowserInspector, check_automation_permission_granted

AppleUIInspector = MacOSAppAndBrowserInspector

__all__ = [
    "AppKitKeyboardBackend",
    "MacKeyboardBackend",
    "MacMouseBackend",
    "MacScreenshotBackend",
    "is_app_visible",
    "MacOSAppAndBrowserInspector",
    "AppleUIInspector",
    "check_automation_permission_granted",
]
