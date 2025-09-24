"""Observer package orchestrating platform-specific implementations."""

from __future__ import annotations

import sys
from typing import Callable

from .base import Observer
from .base.screen import Screen as BaseScreen
from .base.keyboard import KeyboardBackend
from .base.mouse import MouseBackend
from .base.screenshots import ScreenshotBackend
from .fallback import (
    FallbackAppAndBrowserInspector,
    FallbackScreenshotBackend,
    PynputKeyboardBackend,
    PynputMouseBackend,
    fallback_check_automation_permission_granted,
)

AppAndBrowserInspector = FallbackAppAndBrowserInspector
check_automation_permission_granted = fallback_check_automation_permission_granted
keyboard_factory: Callable[[], KeyboardBackend] = lambda: PynputKeyboardBackend()
mouse_factory: Callable[[], MouseBackend] = lambda: PynputMouseBackend()
screenshot_factory: Callable[[], ScreenshotBackend] = FallbackScreenshotBackend
visibility_guard = None

if sys.platform == "darwin":  # macOS
    try:
        from .macos.keyboard import MacKeyboardBackend
        from .macos.mouse import MacMouseBackend
        from .macos.screenshots import MacScreenshotBackend, is_app_visible
        from .macos.app_and_browser_logging import MacOSAppAndBrowserInspector
        from .macos.app_and_browser_logging import check_automation_permission_granted as mac_check_automation_permission_granted
    except Exception:
        AppAndBrowserInspector = FallbackAppAndBrowserInspector
    else:
        AppAndBrowserInspector = MacOSAppAndBrowserInspector
        check_automation_permission_granted = mac_check_automation_permission_granted

        keyboard_factory = lambda: MacKeyboardBackend()
        mouse_factory = lambda: MacMouseBackend()
        screenshot_factory = MacScreenshotBackend
        visibility_guard = is_app_visible
elif sys.platform.startswith("win"):
    try:
        from .windows.keyboard import WindowsKeyboardBackend
        from .windows.mouse import WindowsMouseBackend
        from .windows.screenshots import WindowsScreenshotBackend
        from .windows.app_and_browser_logging import WindowsAppAndBrowserInspector
        from .windows.app_and_browser_logging import (
            check_automation_permission_granted as windows_check_automation_permission_granted,
        )
    except Exception:
        check_automation_permission_granted = fallback_check_automation_permission_granted
    else:
        keyboard_factory = lambda: WindowsKeyboardBackend()
        mouse_factory = lambda: WindowsMouseBackend()
        screenshot_factory = WindowsScreenshotBackend
        AppAndBrowserInspector = WindowsAppAndBrowserInspector
        check_automation_permission_granted = windows_check_automation_permission_granted
elif "check_automation_permission_granted" not in globals():
    check_automation_permission_granted = fallback_check_automation_permission_granted


class Screen(BaseScreen):
    """Concrete screen observer wired with the detected platform backends."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            keyboard_backend=keyboard_factory(),
            mouse_backend=mouse_factory(),
            screenshot_backend_factory=screenshot_factory,
            visibility_guard=visibility_guard,
            *args,
            **kwargs,
        )


__all__ = ["Observer", "Screen", "AppAndBrowserInspector", "check_automation_permission_granted"]
