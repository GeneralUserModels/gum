from __future__ import annotations

import json
import logging
import os
import plistlib
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from typing import Any

import threading
from collections import deque

from ...observers.macos import AppleUIInspector, check_automation_permission_granted
from ...observers.macos.keyboard import event_token_from_nsevent, register_appkit_key_monitors, remove_appkit_monitors
from ...cli.background import BackgroundRecorder
from ...observers.constants import KEYBOARD_PUMP_INTERVAL_MS, PERMISSION_REFRESH_INTERVAL_MS

try:  # AppKit is only available on macOS
    from AppKit import NSEvent, NSEventMaskKeyDown, NSEventMaskKeyUp
except Exception:  # pragma: no cover - AppKit unavailable outside macOS
    NSEvent = None
    NSEventMaskKeyDown = 0
    NSEventMaskKeyUp = 0


DEFAULT_SETTINGS = {
    "output_dir": os.path.join(
        os.path.expanduser("~/Library/Application Support"),
        "Gum Recorder",
    ),
    "onboarding_done": False,
}


class MainThreadKeyboardRecorderShim:
    """We need a small shim running in the main thread to forward keyboard events to the recorder
    because on MacOS there is a security sandbox that prevents background threads from
    listening to keyboard events.
    """

    def __init__(self) -> None:
        self._monitors: list[Any] = []
        self._queue: deque[tuple[str, str]] = deque()
        self._lock = threading.Lock()
        self._running = False

    @staticmethod
    def _event_token(ev) -> str:
        # Delegate to shared backend helper to avoid duplication
        try:
            return event_token_from_nsevent(ev)
        except Exception:
            return "KEY:unknown"

    def start(self) -> bool:
        if self._running:
            return True
        if NSEvent is None:
            logging.getLogger("GumUI").warning("AppKit unavailable; falling back to background keyboard monitor")
            return False

        def _enqueue(token: str, kind: str) -> None:
            if not token:
                return
            with self._lock:
                self._queue.append((token, kind))

        def on_down(ev):
            _enqueue(self._event_token(ev), "press")

        def on_up(ev):
            _enqueue(self._event_token(ev), "release")

        try:
            self._monitors = register_appkit_key_monitors(on_down, on_up)
            self._running = True
        except Exception:
            self._monitors = []
            self._running = False
            logging.getLogger("GumUI").warning(
                "Failed to start main-thread keyboard monitor; falling back to background listener",
                exc_info=True,
            )

        return self._running

    def stop(self) -> None:
        if not self._running:
            return
        try:
            remove_appkit_monitors(self._monitors)
        finally:
            self._monitors = []
            self._running = False
            with self._lock:
                self._queue.clear()

    def pump_main_thread_tasks(self) -> None:
        if not self._running:
            return
        events: list[tuple[str, str]]
        with self._lock:
            if not self._queue:
                return
            events = list(self._queue)
            self._queue.clear()
        for token, kind in events:
            BackgroundRecorder.post_key_event(token, "press" if kind == "press" else "release")


class Tooltip:
    """Simple tooltip helper for Tk widgets."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 400) -> None:
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id: int | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._enter)
        widget.bind("<Leave>", self._leave)
        widget.bind("<ButtonPress>", self._leave)

    def _enter(self, _event=None) -> None:
        self._schedule()

    def _leave(self, _event=None) -> None:
        self._unschedule()
        self._hide()

    def _schedule(self) -> None:
        self._unschedule()
        self._after_id = self.widget.after(self.delay, self._show)

    def _unschedule(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:  # pragma: no cover - best effort cleanup
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip or not self.text:
            return
        try:
            x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, "bbox") else (0, 0, 0, 0)
        except Exception:
            x, y = 0, 0
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            wraplength=320,
        )
        label.pack(ipadx=6, ipady=3)
        self._tip = tip

    def _hide(self) -> None:
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
            self._tip = None


PERMISSION_TOOLTIPS: dict[str, str] = {
    "screen": (
        "macOS requires the Screen Recording permission so Gum Recorder can capture "
        "the pixels on your display. Click 'Open' to open the System dialog and click the '+' button. "
        "This will give you a file dropdown: find and select Gum Recorder to add these permissions. "
        "if it is not already listed. If it is already listed, and you still don't see permissions, click 'Refresh' to update the list or file a ticket."
    ),
    "accessibility": (
        "macOS requires the Accessibility permission so Gum Recorder can observe UI events, including keystrokes. "
        "Click 'Open' to open the System dialog and click the '+' button. "
        "This will give you a file dropdown: find and select Gum Recorder to add these permissions. "
        "if it is not already listed. If it is already listed, and you still don't see permissions, click 'Refresh' to update the list or file a ticket."
    ),
    "input": (
        "Input Monitoring permission is necessary for listening to keyboard events while recording. "
        "Click 'Open' to open the System dialog and click the '+' button. "
        "This will give you a file dropdown: find and select Gum Recorder to add these permissions. "
        "if it is not already listed. If it is already listed, and you still don't see permissions, click 'Refresh' to update the list or file a ticket."
    ),
    "automation": (
        "Browser URL capture relies on macOS Automation (Apple Events). After you click Enable Browser URLs, approve the prompts "
        "and make sure Gum Recorder — or 'osascript' if you launched from Terminal — stays enabled under Privacy & Security → Automation."
    ),
}


BROWSER_AUTOMATION_SCRIPTS: list[tuple[str, str, str]] = [
    ("Safari", "Safari.app", 'tell application "Safari" to return name'),
    ("Google Chrome", "Google Chrome.app", 'tell application "Google Chrome" to return name'),
    ("Chromium", "Chromium.app", 'tell application "Chromium" to return name'),
    ("Brave Browser", "Brave Browser.app", 'tell application "Brave Browser" to return name'),
    ("Microsoft Edge", "Microsoft Edge.app", 'tell application "Microsoft Edge" to return name'),
    ("Arc", "Arc.app", 'tell application "Arc" to return name'),
]


AUTOMATION_APP_LOCATIONS = ["/Applications", os.path.expanduser("~/Applications")]


def load_settings(settings_path: str, default_output_dir: str) -> dict[str, Any]:
    try:
        with open(settings_path, "r") as fh:
            data = json.load(fh)
            if "output_dir" not in data:
                data["output_dir"] = default_output_dir
            if "onboarding_done" not in data:
                data["onboarding_done"] = False
            return data
    except Exception:
        return {
            "output_dir": default_output_dir,
            "onboarding_done": False,
        }


def save_settings(settings_path: str, data: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w") as fh:
            json.dump(data, fh, indent=2)
    except Exception:  # pragma: no cover - best effort persistence
        pass


def format_output_dir(path: str, max_len: int = 64) -> str:
    normalized = os.path.abspath(os.path.expanduser(path))
    if len(normalized) <= max_len:
        return normalized
    head = max_len // 2 - 1
    tail = max_len - head - 1
    return normalized[:head] + "…" + normalized[-tail:]


# ─────────────────────────────── macOS helpers
def open_uri(uri: str) -> None:
    try:
        subprocess.Popen(["open", uri])
    except Exception:  # pragma: no cover - best effort
        pass


def open_screen_recording_settings() -> None:
    open_uri("x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")


def open_accessibility_settings() -> None:
    open_uri("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")


def open_keyboard_monitoring_settings() -> None:
    open_uri("x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")


def open_automation_settings() -> None:
    open_uri("x-apple.systempreferences:com.apple.preference.security?Privacy_Automation")


def open_screen_recording_help() -> None:
    open_uri("https://support.apple.com/guide/mac-help/allow-apps-to-use-screen-and-audio-recording-mchl592e5686/26/mac/26")


def open_accessibility_help() -> None:
    open_uri("https://support.apple.com/guide/mac-help/allow-accessibility-apps-to-access-your-mac-mh43185/26/mac/26")


def open_input_monitoring_help() -> None:
    open_uri("https://support.apple.com/guide/mac-help/control-access-to-input-monitoring-on-mac-mchl4cedafb6/26/mac/26")


def open_automation_help() -> None:
    open_uri("https://support.apple.com/guide/mac-help/allow-apps-to-control-your-mac-mchl30d1931e/mac")


def check_screen_recording_granted() -> bool | None:
    try:
        import Quartz

        if hasattr(Quartz, "CGPreflightScreenCaptureAccess"):
            return bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:
        return None
    return None


def request_screen_recording_access() -> None:
    _request_screen_recording_access(open_settings=True)


def _request_screen_recording_access(open_settings: bool) -> bool:
    triggered = False
    try:
        import Quartz

        request = getattr(Quartz, "CGRequestScreenCaptureAccess", None)
        if callable(request):
            try:
                request()
            except TypeError:
                request(None)
            triggered = True
    except Exception:  # Catches screen recording permission failures
        pass

    if open_settings:
        open_screen_recording_settings()

    return triggered


def prime_screen_recording_permission(logger: logging.Logger | None = None) -> bool:
    logger = logger or logging.getLogger("gum.ui.screen_preflight")
    status = check_screen_recording_granted()
    if status is True:
        logger.debug("Screen Recording permission already granted; skipping preflight")
        return False

    triggered = _request_screen_recording_access(open_settings=False)
    if triggered:
        logger.debug("Triggered Screen Recording permission prompt via preflight")
    else:
        logger.debug("Unable to trigger Screen Recording preflight (API unavailable or call failed)")
    return triggered


def check_accessibility_granted() -> bool | None:
    try:
        import Quartz

        if hasattr(Quartz, "AXIsProcessTrusted"):
            return bool(Quartz.AXIsProcessTrusted())
        if hasattr(Quartz, "AXIsProcessTrustedWithOptions"):
            return bool(Quartz.AXIsProcessTrustedWithOptions(None))
    except Exception:
        return None
    return None


def prompt_accessibility_access() -> None:
    _prompt_accessibility_access(open_settings=True)


def _prompt_accessibility_access(open_settings: bool) -> bool:
    triggered = False
    try:
        import Quartz

        if hasattr(Quartz, "AXIsProcessTrustedWithOptions"):
            from Foundation import NSDictionary

            options = {"kAXTrustedCheckOptionPrompt": True}
            Quartz.AXIsProcessTrustedWithOptions(
                NSDictionary.dictionaryWithDictionary_(options)
            )
            triggered = True
    except Exception:  # Catches accessibility permission failures
        pass

    if open_settings:
        open_accessibility_settings()

    return triggered


def prime_accessibility_permission(logger: logging.Logger | None = None) -> bool:
    logger = logger or logging.getLogger("gum.ui.accessibility_preflight")
    status = check_accessibility_granted()
    if status is True:
        logger.debug("Accessibility permission already granted; skipping preflight")
        return False

    triggered = _prompt_accessibility_access(open_settings=False)
    if triggered:
        logger.debug("Triggered Accessibility permission prompt via preflight")
    else:
        logger.debug("Unable to trigger Accessibility preflight (API unavailable or call failed)")
    return triggered


def check_input_monitoring_granted() -> bool | None:
    try:
        import Quartz

        if hasattr(Quartz, "CGPreflightListenEventAccess"):
            return bool(Quartz.CGPreflightListenEventAccess())

        mask = (1 << Quartz.kCGEventKeyDown) | (1 << Quartz.kCGEventKeyUp)
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            None,
            None,
        )
        if tap is None:
            return False
        try:
            Quartz.CFRelease(tap)
        except Exception:  # Catches input monitoring permission preflight failures
            pass
        return True
    except Exception:
        return None


def prompt_input_monitoring_access() -> None:
    _request_input_monitoring_access(open_settings=True)


def _request_input_monitoring_access(open_settings: bool) -> bool:
    triggered = False
    try:
        import Quartz

        request = getattr(Quartz, "CGRequestListenEventAccess", None)
        if callable(request):
            try:
                request()
            except TypeError:
                request(None)
            triggered = True
    except Exception:  # Catches input monitoring permission preflight failures
        pass

    if open_settings:
        open_keyboard_monitoring_settings()

    return triggered


def prime_input_monitoring_permission(logger: logging.Logger | None = None) -> bool:
    logger = logger or logging.getLogger("gum.ui.input_preflight")
    status = check_input_monitoring_granted()
    if status is True:
        logger.debug("Input Monitoring permission already granted; skipping preflight")
        return False

    triggered = _request_input_monitoring_access(open_settings=False)
    if triggered:
        logger.debug("Triggered Input Monitoring permission prompt via preflight")
    else:
        logger.debug("Unable to trigger Input Monitoring preflight (API unavailable or call failed)")
    return triggered


def check_automation_granted() -> bool | None:
    return check_automation_permission_granted()


def prompt_automation_access() -> None:
    inspector = None
    running_snapshot: list[tuple[str, str, str]] = []
    status_before = check_automation_permission_granted(force_refresh=True)

    if AppleUIInspector is not None:
        try:
            inspector = AppleUIInspector(logging.getLogger("gum.ui.automation_prompt"))
            running_snapshot = list(inspector.running_browser_applications())
        except Exception:  # Catches automation permission preflight failures
            inspector = None
            running_snapshot = []

    used_new_path = False
    if inspector is not None:
        try:
            used_new_path = inspector.prime_automation_for_running_browsers()
            if used_new_path:
                status_check = check_automation_permission_granted(force_refresh=True)
                if status_check is not True:
                    used_new_path = False
        except Exception:  # Catches automation permission preflight failures
            used_new_path = False

    if not used_new_path:
        _legacy_trigger_automation_scripts()

    status_after = check_automation_permission_granted(force_refresh=True)
    notes = _collect_automation_guidance(status_before, status_after, inspector, running_snapshot)
    if status_after is not True and notes:
        _show_automation_guidance(notes)

    open_automation_settings()


def _legacy_trigger_automation_scripts() -> None:
    def _app_installed(bundle_name: str) -> bool:
        for base in AUTOMATION_APP_LOCATIONS:
            if os.path.exists(os.path.join(base, bundle_name)):
                return True
        return False

    any_triggered = False
    for _label, bundle, script in BROWSER_AUTOMATION_SCRIPTS:
        if not _app_installed(bundle):
            continue
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            any_triggered = True
        except Exception:  # Catches automation permission preflight failures
            continue

    if not any_triggered:
        try:
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to return 1'],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
        except Exception:  # Catches automation permission preflight failures
            pass


def prime_automation_permissions(logger: logging.Logger | None = None) -> None:
    if AppleUIInspector is None:
        _legacy_trigger_automation_scripts()
        return
    try:
        inspector = AppleUIInspector(logger or logging.getLogger("gum.ui.automation_preflight"))
        attempted = inspector.prime_automation_for_running_browsers()
        if not attempted and check_automation_permission_granted(force_refresh=True) is not True:
            _legacy_trigger_automation_scripts()
    except Exception:  # Catches automation permission preflight failures
        _legacy_trigger_automation_scripts()


def _collect_automation_guidance(status_before: bool | None, status_after: bool | None, inspector: AppleUIInspector | None, running_snapshot: list[tuple[str, str, str]]) -> list[str]:
    notes: list[str] = []

    sig_info = _analyze_code_signature()
    binary_path = sig_info.get("binary")
    bundle_path = sig_info.get("bundle")
    signed = sig_info.get("signed")
    has_entitlement = sig_info.get("has_automation_entitlement")
    codesign_error = sig_info.get("codesign_error")

    if getattr(sys, "frozen", False):
        target_path = bundle_path or binary_path
        if signed is False:
            if target_path:
                notes.append(
                    f"Code-sign the app at {target_path} (ad-hoc signing works) so macOS can request Automation. Example: `codesign --force --deep --options runtime --sign - '{target_path}'`."
                )
            else:
                notes.append("Code-sign the running app with the Hardened Runtime and Apple Events entitlement so macOS can show the Automation prompt.")
        elif signed and not has_entitlement:
            notes.append(
                "The current build is signed without the com.apple.security.automation.apple-events entitlement. Add that entitlement and rebuild/sign before retrying."
            )
        elif codesign_error:
            notes.append(codesign_error)
    else:
        notes.append(
            "You're running the recorder from source. macOS will attribute the Automation request to `osascript`. Approve 'osascript' under Privacy & Security → Automation or build a signed app when you're ready."
        )

    quarantine_path = bundle_path or (binary_path if getattr(sys, "frozen", False) else None)
    if quarantine_path and _has_quarantine_attribute(quarantine_path):
        notes.append(f"Remove the quarantine attribute with `xattr -dr com.apple.quarantine '{quarantine_path}'` and relaunch.")

    running = list(running_snapshot)
    if not running and inspector is not None:
        try:
            running = list(inspector.running_browser_applications())
        except Exception:  # Catches automation permission preflight failures
            running = []
    if not running:
        notes.append("Open Safari, Chrome, Brave, Edge, or Arc and leave a window active before enabling browser URLs.")

    if status_after is False or status_before is False:
        bundle_id = _detect_bundle_identifier(bundle_path)
        if not getattr(sys, "frozen", False):
            target = "com.apple.osascript"
        else:
            target = bundle_id or "Gum Recorder"
        notes.append(f"macOS has a previous Automation denial recorded. Run `tccutil reset AppleEvents {target}` and relaunch the app.")

    return _dedupe_preserve_order(notes)


def _show_automation_guidance(notes: list[str]) -> None:
    if not notes:
        return
    try:
        from tkinter import messagebox
    except Exception:
        logging.getLogger("gum.ui.automation_prompt").info("Automation guidance: %s", " | ".join(notes))
        return

    body = "\n\n".join(notes)
    message = "Automation permission is still unavailable. Try the steps below:\n\n" + body
    messagebox.showinfo("Enable Browser URLs", message)


def _analyze_code_signature() -> dict[str, Any]:
    binary_path, bundle_path = _current_binary_paths()
    info: dict[str, Any] = {
        "binary": binary_path,
        "bundle": bundle_path,
        "signed": None,
        "has_automation_entitlement": None,
        "codesign_error": None,
    }

    if not getattr(sys, "frozen", False) or binary_path is None:
        return info

    try:
        proc = subprocess.run(
            ["codesign", "--display", "--entitlements", "-", str(binary_path)],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except FileNotFoundError:
        info["codesign_error"] = "The `codesign` tool is not available in PATH; unable to verify entitlements."
        return info
    except Exception as exc:
        info["codesign_error"] = f"Failed to inspect code signature: {exc}"
        return info

    if proc.returncode != 0:
        info["signed"] = False
        info["codesign_error"] = (proc.stderr or proc.stdout or "Code signature check failed").strip()
        return info

    info["signed"] = True
    ent_blob = (proc.stdout or proc.stderr or "").lower()
    info["has_automation_entitlement"] = "com.apple.security.automation.apple-events" in ent_blob
    return info


def _current_binary_paths() -> tuple[Path | None, Path | None]:
    try:
        if getattr(sys, "frozen", False):
            binary = Path(sys.executable).resolve()
        else:
            binary = Path(__file__).resolve()
    except Exception:
        binary = None

    bundle = None
    if binary is not None:
        for parent in binary.parents:
            if parent.suffix == ".app":
                bundle = parent
                break
    return binary, bundle


def _has_quarantine_attribute(path: Path) -> bool:
    try:
        proc = subprocess.run(
            ["xattr", "-p", "com.apple.quarantine", str(path)],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return proc.returncode == 0


def _detect_bundle_identifier(bundle_path: Path | None) -> str | None:
    if bundle_path:
        plist_path = bundle_path / "Contents" / "Info.plist"
        try:
            with open(plist_path, "rb") as fh:
                data = plistlib.load(fh)
                bundle_id = data.get("CFBundleIdentifier")
                if isinstance(bundle_id, str) and bundle_id.strip():
                    return bundle_id.strip()
        except Exception:
            pass
    env_bundle = os.environ.get("GUM_BUNDLE_ID")
    if env_bundle:
        return env_bundle
    return None


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
