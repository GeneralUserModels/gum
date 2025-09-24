"""Platform-agnostic observer helpers and fallbacks."""

from .keyboard import PynputKeyboardBackend
from .mouse import PynputMouseBackend
from .screenshots import FallbackScreenshotBackend
from .app_and_browser_logging import (
    FallbackAppAndBrowserInspector,
    check_automation_permission_granted as fallback_check_automation_permission_granted,
)

__all__ = [
    "PynputKeyboardBackend",
    "PynputMouseBackend",
    "FallbackScreenshotBackend",
    "FallbackAppAndBrowserInspector",
    "fallback_check_automation_permission_granted",
]
