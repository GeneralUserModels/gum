"""Platform-specific application support for Gum."""

from .macos import AppleUIInspector, check_automation_permission_granted

__all__ = [
    "AppleUIInspector",
    "check_automation_permission_granted",
]
