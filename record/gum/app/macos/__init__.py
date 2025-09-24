"""macOS-specific application entrypoints and utilities for Gum."""

from ...observers.macos import AppleUIInspector, check_automation_permission_granted

__all__ = [
    "AppleUIInspector",
    "check_automation_permission_granted",
]
