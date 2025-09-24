from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import Quartz
except Exception:
    Quartz = None

try:
    from AppKit import NSWorkspace, NSRunningApplication
except Exception:
    NSWorkspace = None
    NSRunningApplication = None


__all__ = [
    "MacOSAppAndBrowserInspector",
    "check_automation_permission_granted",
]


SYSTEM_WINDOW_OWNERS = {"dock", "windowserver", "window server"}
OVERLAY_WINDOW_OWNERS = {
    "control center",
    "notification center",
    "notificationcentre",
    "notificationcentreui",
    "screen recording",
    "screenrecording",
    "screenrecordingindicator",
    "screenrecordingui",
    "screencapture",
    "screenshotui",
    "siri",
}


def _visible_tab_jxa_script(app_title: str, tab_accessor: str) -> str:
    """Generate a JavaScript for Automation (JXA) script to get the URL of the foremost visible tab.
    
    This function creates a robust JXA script that finds the most prominent browser window
    and extracts the URL from its active tab. It's used for browsers that support JXA
    automation and provides more reliable tab detection than simple AppleScript.
    
    The script handles various edge cases:
    - Multiple windows with different visibility states
    - Minimized or hidden windows
    - Different tab accessor methods (activeTab vs currentTab)
    
    Args:
        app_title: The application name (e.g., "Safari", "Google Chrome")
        tab_accessor: The method to access the active tab (e.g., "activeTab", "currentTab")
        
    Returns:
        A complete JXA script as a string
    """
    return (
        "jxa:(() => {\n"
        f"  const app = Application(\"{app_title}\");\n"
        "  if (!app.running()) { return null; }\n"
        "  const wins = app.windows();\n"
        "  if (!wins.length) { return null; }\n"
        "  const ordered = wins\n"
        "    .map(win => ({\n"
        "      win,\n"
        "      order: (() => {\n"
        "        try { return win.index(); } catch (err) { return Number.POSITIVE_INFINITY; }\n"
        "      })(),\n"
        "    }))\n"
        "    .sort((a, b) => a.order - b.order);\n"
        "  for (const entry of ordered) {\n"
        "    const win = entry.win;\n"
        "    try { if (win.miniaturized && win.miniaturized()) { continue; } } catch (err) {}\n"
        "    try { if (win.visible && !win.visible()) { continue; } } catch (err) {}\n"
        f"    if (typeof win.{tab_accessor} !== 'function') {{ continue; }}\n"
        "    let tab = null;\n"
        f"    try {{ tab = win.{tab_accessor}(); }} catch (err) {{ tab = null; }}\n"
        "    if (!tab) { continue; }\n"
        "    try {\n"
        "      if (typeof tab.url === 'function') { return tab.url(); }\n"
        "      if (typeof tab.URL === 'function') { return tab.URL(); }\n"
        "    } catch (err) {}\n"
        "  }\n"
        "  return null;\n"
        "})();"
    )


def _chromium_jxa_script(app_title: str) -> str:
    """Generate a JXA script for Chromium-based browsers (Chrome, Edge, Brave, etc.).
    
    Chromium-based browsers use 'activeTab' to access the current tab, which is different
    from Safari's 'currentTab' method. This function creates the appropriate script
    for this browser family.
    
    Args:
        app_title: The application name (e.g., "Google Chrome", "Microsoft Edge")
        
    Returns:
        A JXA script configured for Chromium-based browsers
    """
    return _visible_tab_jxa_script(app_title, "activeTab")


def _safari_jxa_script(app_title: str) -> str:
    """Generate a JXA script for Safari-based browsers.
    
    Safari uses 'currentTab' to access the current tab, which is different from
    Chromium-based browsers. This function creates the appropriate script for
    Safari and Safari Technology Preview.
    
    Args:
        app_title: The application name (e.g., "Safari", "Safari Technology Preview")
        
    Returns:
        A JXA script configured for Safari-based browsers
    """
    return _visible_tab_jxa_script(app_title, "currentTab")


def _focused_app_via_accessibility() -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Attempt to resolve the focused app using the accessibility API 
    (i.e. the app that is currently in the user's foreground, on the monitor they are currently using... this is tricky...).
    
    This function is the primary method for detecting which application currently has
    keyboard focus on macOS. It uses the accessibility API to get the most accurate
    information about the focused application, which is crucial for understanding
    user context and activity tracking.
    
    The function implements a multi-layered approach with extensive error handling:
    
    1. **System-wide Element Creation**: Creates a system-wide accessibility element
       that can query the focused application. This can fail if accessibility
       permissions are not granted.
    
    2. **Focused Application Query**: Uses AXUIElementCopyAttributeValue to get the
       currently focused application reference. Handles different API signatures
       across macOS versions (3-parameter vs 2-parameter versions).
    
    3. **Process ID Extraction**: Gets the process ID from the application reference,
       which is needed for further app information retrieval.
    
    4. **App Information via NSRunningApplication**: Uses AppKit to get detailed
       app information (name, bundle ID) from the process ID. This is the most
       reliable method when available.
    
    5. **Window List Fallback**: If AppKit fails, falls back to querying the window
       list to find the app name by matching the process ID to window owners.
    
    The extensive exception handling ensures the function never crashes, even when:
    - Accessibility permissions are denied
    - Apps quit or change focus during execution
    - Different macOS versions have API variations
    - System is in various states (sleep, locked, etc.)
    
    Returns:
        Tuple of (app_name, bundle_id, pid):
        - app_name: Human-readable application name (e.g., "Safari", "Google Chrome")
        - bundle_id: Application bundle identifier (e.g., "com.apple.safari")
        - pid: Process ID of the application
        
        All values may be None if detection fails at any stage.
    """

    if Quartz is None:
        return None, None, None

    required = (
        "AXUIElementCreateSystemWide",
        "AXUIElementCopyAttributeValue",
        "AXUIElementGetPid",
        "kAXFocusedApplicationAttribute",
        "kAXErrorSuccess",
    )
    if any(not hasattr(Quartz, attr) for attr in required):
        return None, None, None

    try:
        system = Quartz.AXUIElementCreateSystemWide()
    except Exception:  # Catches accessibility permission denied, system-level failures
        return None, None, None

    if system is None:
        return None, None, None

    try:
        result = Quartz.AXUIElementCopyAttributeValue(
            system,
            Quartz.kAXFocusedApplicationAttribute,
            None,
        )
    except TypeError:  # Catches API signature mismatch (3-param vs 2-param versions)
        try:
            result = Quartz.AXUIElementCopyAttributeValue(
                system,
                Quartz.kAXFocusedApplicationAttribute,
            )
        except Exception:  # Catches any failure in the 2-parameter fallback
            return None, None, None
    except Exception:  # Catches accessibility API failures, permission issues
        return None, None, None

    if isinstance(result, tuple):
        app_ref, error = result
        if error not in (None, Quartz.kAXErrorSuccess):
            return None, None, None
    else:
        app_ref = result

    if app_ref is None:
        return None, None, None

    try:
        pid = Quartz.AXUIElementGetPid(app_ref)
    except Exception:  # Catches invalid app reference, terminated processes
        pid = None

    if not pid:
        return None, None, None

    name: Optional[str] = None
    bundle: Optional[str] = None

    if NSRunningApplication is not None:
        try:
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        except Exception:  # Catches invalid PID, app quit, AppKit failures
            app = None
        if app is not None:
            bundle_candidate = (app.bundleIdentifier() or "").strip() or None
            name_candidate = (app.localizedName() or "").strip() or None
            bundle = bundle_candidate or bundle
            name = name_candidate or bundle_candidate or name
            if name:
                return name, bundle, pid

    try:
        opts = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListOptionIncludingWindow
        )
        wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
        for info in wins:
            if info.get("kCGWindowOwnerPID") == pid:
                owner = (info.get("kCGWindowOwnerName") or "").strip()
                bundle_candidate = (info.get("kCGWindowOwnerBundleIdentifier") or "").strip() or None
                if owner:
                    return owner, (bundle_candidate or bundle), pid
    except Exception:  # Catches window list API failures, system state issues
        pass

    return None, bundle, pid


BROWSER_OSA_SCRIPTS: dict[str, tuple[str, ...]] = {
    "safari": (
        _safari_jxa_script("Safari"),
        'tell application "Safari" to if (exists front document) then get URL of front document',
        'tell application "Safari" to if (count of documents) > 0 then get URL of front document',
        'jxa:(() => {\n  const safari = Application("Safari");\n  if (!safari.running()) { return null; }\n  const docs = safari.documents();\n  return docs.length ? docs[0].url() : null;\n})();',
    ),
    "safari technology preview": (
        _safari_jxa_script("Safari Technology Preview"),
        'tell application "Safari Technology Preview" to if (exists front document) then get URL of front document',
        'jxa:(() => {\n  const safari = Application("Safari Technology Preview");\n  if (!safari.running()) { return null; }\n  const docs = safari.documents();\n  return docs.length ? docs[0].url() : null;\n})();',
    ),
    "google chrome": (
        _chromium_jxa_script("Google Chrome"),
        'tell application "Google Chrome" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "google chrome beta": (
        _chromium_jxa_script("Google Chrome Beta"),
        'tell application "Google Chrome Beta" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "google chrome dev": (
        _chromium_jxa_script("Google Chrome Dev"),
        'tell application "Google Chrome Dev" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "google chrome canary": (
        _chromium_jxa_script("Google Chrome Canary"),
        'tell application "Google Chrome Canary" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "chromium": (
        _chromium_jxa_script("Chromium"),
        'tell application "Chromium" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "brave browser": (
        _chromium_jxa_script("Brave Browser"),
        'tell application "Brave Browser" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "brave browser beta": (
        _chromium_jxa_script("Brave Browser Beta"),
        'tell application "Brave Browser Beta" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "brave browser nightly": (
        _chromium_jxa_script("Brave Browser Nightly"),
        'tell application "Brave Browser Nightly" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "microsoft edge": (
        _chromium_jxa_script("Microsoft Edge"),
        'tell application "Microsoft Edge" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "microsoft edge beta": (
        _chromium_jxa_script("Microsoft Edge Beta"),
        'tell application "Microsoft Edge Beta" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "microsoft edge dev": (
        _chromium_jxa_script("Microsoft Edge Dev"),
        'tell application "Microsoft Edge Dev" to if (count of windows) > 0 then get URL of active tab of front window',
    ),
    "arc": (
        _chromium_jxa_script("Arc"),
        'tell application "Arc"\nif (count of windows) = 0 then return missing value\nreturn URL of active tab of front window\nend tell',
        'tell application "Arc"\nif (count of windows) = 0 then return missing value\ntell front window to tell active tab to return URL\nend tell',
        'jxa:(() => {\n  const arc = Application("Arc");\n  const wins = arc.windows();\n  if (!wins.length) { return null; }\n  const front = arc.frontWindow();\n  if (!front) { return null; }\n  const tab = front.activeTab();\n  return tab ? tab.url() : null;\n})();',
    ),
}

BROWSER_BUNDLE_IDS: dict[str, str] = {
    "com.apple.safari": "safari",
    "com.apple.safaritechnologypreview": "safari technology preview",
    "com.google.chrome": "google chrome",
    "com.google.chrome.beta": "google chrome beta",
    "com.google.chrome.dev": "google chrome dev",
    "com.google.chrome.canary": "google chrome canary",
    "org.chromium.chromium": "chromium",
    "com.brave.browser": "brave browser",
    "com.brave.browser.beta": "brave browser beta",
    "com.brave.browser.nightly": "brave browser nightly",
    "com.microsoft.edgemac": "microsoft edge",
    "com.microsoft.edgemac.beta": "microsoft edge beta",
    "com.microsoft.edgemac.dev": "microsoft edge dev",
    "company.thebrowser.browser": "arc",
}



AUTOMATION_PERMISSION_CACHE_TTL = 3.0
_AUTOMATION_PERMISSION_CACHE: tuple[float, bool | None] | None = None
_AUTOMATION_DENIED_SUBSTRINGS = (
    "-1743",
    "not authorized to send apple events",
    "not authorised to send apple events",
    "errae eventnotpermitted",
)

_NULL_URL_VALUES = {
    "",
    "null",
    "missing value",
    "undefined",
}


def _ax_copy_attribute(element, attribute):
    """Safely copy an attribute value from an accessibility element.
    
    This helper function provides robust access to accessibility element attributes
    with proper error handling for different API versions and failure modes.
    It's used throughout the accessibility-based app detection system.
    
    Args:
        element: The accessibility element to query
        attribute: The attribute name to retrieve
        
    Returns:
        The attribute value, or None if retrieval fails
    """
    if Quartz is None:
        return None
    try:
        value = Quartz.AXUIElementCopyAttributeValue(element, attribute, None)
    except TypeError:
        try:
            value = Quartz.AXUIElementCopyAttributeValue(element, attribute)
        except Exception:
            return None
    except Exception:
        return None
    if isinstance(value, tuple):
        candidate, error = value
        if error not in (None, getattr(Quartz, "kAXErrorSuccess", None)):
            return None
        value = candidate
    return value


def _browser_url_via_accessibility(pid: Optional[int]) -> Optional[str]:
    """Extract browser URL using accessibility API as a fallback method.
    
    This function provides an alternative method to get browser URLs when AppleScript
    automation fails or is not available. It uses the accessibility API to find the
    focused window and extract URL information from browser applications.
    
    This is particularly useful for:
    - Browsers that don't support AppleScript automation
    - Systems where automation permissions are denied
    - Fallback when primary URL extraction methods fail
    
    Args:
        pid: Process ID of the browser application
        
    Returns:
        The current URL from the browser, or None if extraction fails
    """
    if Quartz is None or not pid:
        return None
    try:
        app_elem = Quartz.AXUIElementCreateApplication(pid)
    except Exception:
        return None
    if app_elem is None:
        return None

    window = _ax_copy_attribute(app_elem, "AXFocusedWindow")
    if window is None:
        return None

    for attr in ("AXURL", "AXDocument"):
        value = _ax_copy_attribute(window, attr)
        if value is None:
            continue
        if isinstance(value, str):
            if value:
                return value
            continue
        try:
            string_value = str(value)
        except Exception:
            continue
        if string_value:
            return string_value
    return None


@dataclass
class MacOSAppAndBrowserInspector:
    """macOS-specific implementation for detecting applications and extracting browser URLs.
    
    This class provides comprehensive app and browser detection capabilities for macOS,
    enabling the recording system to understand what applications users are interacting
    with and what web pages they're viewing. It's a critical component of the user
    activity tracking system.
    
    Key capabilities:
    - Detect the currently focused/active application
    - Extract URLs from browser applications using AppleScript automation
    - Fallback to accessibility API when automation is not available
    - Handle automation permission management and error reporting
    - Support for major browsers (Safari, Chrome, Edge, Brave, Arc, etc.)
    
    The class maintains state to optimize performance and provide consistent results
    across multiple queries, including caching of browser URLs and tracking of
    permission issues.
    """
    logger: logging.Logger
    last_frontmost_bundle_id: Optional[str] = None
    last_frontmost_pid: Optional[int] = None
    last_browser_urls: dict[str, str] = field(default_factory=dict)
    unknown_browser_apps: set[str] = field(default_factory=set)
    browser_script_failures: set[tuple[str, str, int]] = field(default_factory=set)
    automation_denied_for: set[str] = field(default_factory=set)

    def app_at_point(self, x: float, y: float) -> tuple[Optional[str], Optional[str]]:
        """Determine which application owns the window at the given screen coordinates.
        
        This method is used to identify which app the user is interacting with when they
        click or interact at specific screen coordinates. It's part of the app detection
        system that helps track user activity across different applications.
        
        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
            
        Returns:
            Tuple of (app_name, bundle_id) for the app at the given point, or (None, None) if not found
        """
        if Quartz is None:
            return None, None

        try:
            wins = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListOptionIncludingWindow,
                Quartz.kCGNullWindowID,
            ) or []
        except Exception:
            return None, None

        for info in wins:
            owner = info.get("kCGWindowOwnerName") or ""
            owner_lower = owner.lower()
            if not owner or owner_lower in SYSTEM_WINDOW_OWNERS or owner_lower in OVERLAY_WINDOW_OWNERS:
                continue

            bounds = info.get("kCGWindowBounds") or {}
            left = int(bounds.get("X", 0) or 0)
            top = int(bounds.get("Y", 0) or 0)
            width = int(bounds.get("Width", 0) or 0)
            height = int(bounds.get("Height", 0) or 0)
            if width <= 0 or height <= 0:
                continue

            if not (left <= int(x) < left + width and top <= int(y) < top + height):
                continue

            bundle = (info.get("kCGWindowOwnerBundleIdentifier") or "").strip() or None
            if bundle:
                self.last_frontmost_bundle_id = bundle.lower()
            pid_candidate = info.get("kCGWindowOwnerPID")
            if pid_candidate is not None:
                try:
                    self.last_frontmost_pid = int(pid_candidate)
                except Exception:
                    self.last_frontmost_pid = None
            return owner, bundle

        return None, None

    def get_frontmost_app_name(self) -> Optional[str]:
        """Get the name of the currently focused/active application.
        
        This is the primary method for determining which app the user is currently using.
        It tries multiple approaches in order of reliability:
        1. Accessibility API (most accurate for focused apps)
        2. NSWorkspace frontmostApplication (AppKit fallback)
        3. Window list analysis (finds largest visible window)
        
        The result is used throughout the system to track which application context
        user interactions are happening in, enabling proper app-specific logging.
        
        Returns:
            The name of the frontmost application, or None if detection fails
        """
        name, bundle, pid = _focused_app_via_accessibility()
        if bundle:
            self.last_frontmost_bundle_id = bundle.lower()
        if pid:
            self.last_frontmost_pid = pid
        if name:
            return name

        if NSWorkspace is not None:
            try:
                app = NSWorkspace.sharedWorkspace().frontmostApplication()
                if app is not None:
                    bundle_id = (app.bundleIdentifier() or "").strip() or None
                    self.last_frontmost_bundle_id = bundle_id.lower() if bundle_id else None
                    name = (app.localizedName() or bundle_id or "").strip()
                    if name:
                        return name
            except Exception:
                self.last_frontmost_bundle_id = None

        if Quartz is None:
            self.last_frontmost_bundle_id = None
            return None

        try:
            opts = (
                Quartz.kCGWindowListOptionOnScreenOnly
                | Quartz.kCGWindowListOptionIncludingWindow
            )
            wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
        except Exception:
            self.last_frontmost_bundle_id = None
            return None

        self.last_frontmost_bundle_id = None
        self.last_frontmost_pid = None

        def record_owner(owner: str, info: dict) -> str:
            bundle_candidate = (info.get("kCGWindowOwnerBundleIdentifier") or "").strip() or None
            pid_candidate = info.get("kCGWindowOwnerPID")
            if bundle_candidate:
                self.last_frontmost_bundle_id = bundle_candidate.lower()
            if pid_candidate is not None:
                try:
                    self.last_frontmost_pid = int(pid_candidate)
                except Exception:
                    self.last_frontmost_pid = None
            return owner

        for info in wins:
            owner = info.get("kCGWindowOwnerName") or ""
            owner_lower = owner.lower()
            if not owner or owner_lower in SYSTEM_WINDOW_OWNERS or owner_lower in OVERLAY_WINDOW_OWNERS:
                continue

            layer = info.get("kCGWindowLayer", 0)
            if layer != 0:
                continue

            alpha = info.get("kCGWindowAlpha", 1)
            if alpha == 0:
                continue

            bounds = info.get("kCGWindowBounds") or {}
            width = max(int(bounds.get("Width", 0) or 0), 0)
            height = max(int(bounds.get("Height", 0) or 0), 0)
            if width < 32 or height < 32:
                continue

            return record_owner(owner, info)

        candidate_name: Optional[str] = None
        candidate_info: Optional[dict] = None
        candidate_area = 0

        for info in wins:
            owner = info.get("kCGWindowOwnerName") or ""
            owner_lower = owner.lower()
            if not owner or owner_lower in SYSTEM_WINDOW_OWNERS or owner_lower in OVERLAY_WINDOW_OWNERS:
                continue

            bounds = info.get("kCGWindowBounds") or {}
            width = max(int(bounds.get("Width", 0) or 0), 0)
            height = max(int(bounds.get("Height", 0) or 0), 0)
            area = width * height
            if area <= 0:
                continue

            if area > candidate_area:
                candidate_name = owner
                candidate_info = info
                candidate_area = area

        if candidate_name and candidate_info:
            return record_owner(candidate_name, candidate_info)

        for info in wins:
            owner = info.get("kCGWindowOwnerName") or ""
            owner_lower = owner.lower()
            if owner and owner_lower not in SYSTEM_WINDOW_OWNERS and owner_lower not in OVERLAY_WINDOW_OWNERS:
                return record_owner(owner, info)

        return None

    def get_browser_url(self, app_name: Optional[str]) -> Optional[str]:
        """Get the current URL from a browser application.
        
        This method is the core of browser URL tracking functionality. It determines
        what webpage the user is currently viewing in their browser, which is crucial
        for understanding the context of user interactions (e.g., what site they're
        browsing when they click or type).
        
        The method tries multiple approaches:
        1. AppleScript automation (primary method for most browsers)
        2. Accessibility API fallback (for browsers that don't support AppleScript)
        3. Cached results (for performance)
        
        Args:
            app_name: Name of the browser application to query
            
        Returns:
            The current URL being viewed, or None if not available or not a browser
        """
        if not app_name:
            return None

        log = self.logger
        key = self._resolve_browser_key(app_name)
        if key is None:
            signature = f"{app_name}|{self.last_frontmost_bundle_id or ''}"
            if signature not in self.unknown_browser_apps:
                self.unknown_browser_apps.add(signature)
                log.info(
                    "No browser URL mapping available for '%s' (bundle=%s)",
                    app_name,
                    self.last_frontmost_bundle_id,
                )
            return None

        result = self._run_browser_scripts(app_name, key)
        if result:
            self.last_browser_urls[key] = result
            return result

        fallback = _browser_url_via_accessibility(self.last_frontmost_pid)
        if fallback:
            self.last_browser_urls[key] = fallback
            return fallback

        return self.last_browser_urls.get(key)

    def _run_browser_scripts(self, app_name: str, key: str) -> Optional[str]:
        """Execute AppleScript commands to extract the current URL from a browser.
        
        This method handles the low-level execution of AppleScript commands that query
        browser applications for their current URL. It's a critical component of the
        browser URL tracking system, handling multiple script formats (AppleScript and JXA)
        and managing automation permissions.
        
        The method includes comprehensive error handling for:
        - Automation permission denials
        - Script execution failures
        - Timeout handling
        - Different browser script formats
        
        Args:
            app_name: Human-readable name of the browser application
            key: Internal key identifying the browser type (e.g., 'safari', 'google chrome')
            
        Returns:
            The current URL from the browser, or None if extraction fails
        """
        log = self.logger
        scripts = BROWSER_OSA_SCRIPTS.get(key, ())
        if not scripts:
            if key not in self.unknown_browser_apps:
                self.unknown_browser_apps.add(key)
                log.info("No AppleScript candidates registered for '%s'", key)
            return None

        try:
            for script in scripts:
                cmd = ["osascript"]
                if script.startswith("jxa:"):
                    body = script[4:]
                    cmd.extend(["-l", "JavaScript", "-e", body])
                else:
                    cmd.extend(["-e", script])

                out = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=0.75,
                    check=False,
                )
                stdout = (out.stdout or "").strip()
                if out.returncode == 0 and stdout and stdout.strip().lower() not in _NULL_URL_VALUES:
                    _update_automation_cache(True)
                    self.last_browser_urls[key] = stdout
                    return stdout

                failure_sig = (key, script, out.returncode)
                if failure_sig not in self.browser_script_failures:
                    self.browser_script_failures.add(failure_sig)
                    stderr = (out.stderr or "").strip()
                    if _automation_denied_from_stderr(stderr):
                        _update_automation_cache(False)
                        if key not in self.automation_denied_for:
                            self.automation_denied_for.add(key)
                            log.warning(
                                "Automation permission denied when querying '%s'. "
                                "Enable Gum Recorder (or osascript) in System Settings → Privacy & Security → Automation.",
                                app_name,
                            )
                        return None
                    level = logging.WARNING if out.returncode not in (0, -128) else logging.DEBUG
                    log.log(
                        level,
                        "Browser URL script failed for '%s'. key=%s exit=%s stderr=%s",
                        app_name,
                        key,
                        out.returncode,
                        stderr,
                    )
            return None
        except FileNotFoundError:
            log.warning("'osascript' binary not found when attempting to read browser URL")
            return None
        except subprocess.TimeoutExpired:
            log.debug("Timed out while fetching browser URL for '%s'", app_name)
            return None
        except Exception as exc:
            log.debug("Unexpected error fetching browser URL for '%s': %s", app_name, exc)
            return None

    def running_browser_applications(self) -> list[tuple[str, str, str]]:
        """Get a list of currently running browser applications.
        
        This method scans the system for running browser applications that are known
        to the system. It's used for automation permission testing and for determining
        which browsers are available for URL tracking.
        
        The method identifies browsers by their bundle identifiers and returns
        standardized information about each running browser.
        
        Returns:
            List of tuples containing (app_name, browser_key, bundle_id) for each running browser
        """
        if NSWorkspace is None:
            return []
        try:
            workspace = NSWorkspace.sharedWorkspace()
            running = workspace.runningApplications()
        except Exception:
            return []

        seen: set[str] = set()
        result: list[tuple[str, str, str]] = []
        for app in running:
            try:
                bundle_id = (app.bundleIdentifier() or "").strip().lower()
                if not bundle_id:
                    continue
                key = BROWSER_BUNDLE_IDS.get(bundle_id)
                if not key or key in seen:
                    continue
                name = app.localizedName() or bundle_id
                seen.add(key)
                result.append((name, key, bundle_id))
            except Exception:
                continue
        return result

    def prime_automation_for_running_browsers(self) -> bool:
        """Test automation permissions for running browsers to detect permission issues early.
        
        This method proactively tests AppleScript automation permissions by attempting
        to query each running browser for its URL. This helps identify permission issues
        before the user starts interacting with browsers, providing better error messages
        and user experience.
        
        The method is typically called during system initialization to:
        1. Detect if automation permissions are granted
        2. Cache permission status for performance
        3. Provide early warning about permission issues
        
        Returns:
            True if automation testing was attempted, False if no browsers were running
        """
        log = self.logger
        granted = check_automation_permission_granted()
        if granted:
            log.debug("Automation permission already granted; skipping browser preflight")
            return True

        attempted = False
        for app_name, key, bundle_id in self.running_browser_applications():
            attempted = True
            previous_bundle = self.last_frontmost_bundle_id
            try:
                self.last_frontmost_bundle_id = bundle_id
                self._run_browser_scripts(app_name, key)
            finally:
                self.last_frontmost_bundle_id = previous_bundle

        if not attempted:
            frontmost = self.get_frontmost_app_name()
            if frontmost:
                key = self._resolve_browser_key(frontmost)
                if key:
                    self._run_browser_scripts(frontmost, key)
                    attempted = True
                else:
                    log.debug("Frontmost app '%s' is not a known browser for automation preflight", frontmost)
            else:
                log.debug("No running browsers detected when attempting automation preflight")

        return attempted

    def _resolve_browser_key(self, app_name: str) -> Optional[str]:
        """Convert an application name to a standardized browser key for script lookup.
        
        This method normalizes application names to match the keys used in the
        BROWSER_OSA_SCRIPTS dictionary. It handles various naming variations and
        also checks bundle identifiers as a fallback method for identification.
        
        The normalization process:
        1. Converts to lowercase and removes ".app" suffix
        2. Checks against known browser names
        3. Falls back to bundle identifier matching
        4. Handles variations like "Google Chrome Browser" -> "google chrome"
        
        Args:
            app_name: The application name to resolve
            
        Returns:
            The standardized browser key, or None if not a known browser
        """
        normalized = " ".join(app_name.lower().replace(".app", "").split())
        if normalized in BROWSER_OSA_SCRIPTS:
            return normalized

        bundle = (self.last_frontmost_bundle_id or "").strip().lower()
        if bundle:
            if bundle in BROWSER_BUNDLE_IDS:
                return BROWSER_BUNDLE_IDS[bundle]
            parts = bundle.split('.')
            while len(parts) > 2:
                parts = parts[:-1]
                candidate = '.'.join(parts)
                if candidate in BROWSER_BUNDLE_IDS:
                    return BROWSER_BUNDLE_IDS[candidate]

        if normalized.endswith(" browser"):
            simplified = normalized[:-8]
            if simplified in BROWSER_OSA_SCRIPTS:
                return simplified

        return None





#### 
## four helper functions for checking permission status to help more naive users understand whether their app has permissions.

def _update_automation_cache(value: bool | None) -> None:
    """Update the global automation permission cache with a new value and timestamp.
    
    This function manages the caching of automation permission status to avoid
    repeatedly testing permissions, which can be expensive and slow. The cache
    includes both the permission status and a timestamp for TTL (time-to-live)
    management.
    
    The cache is used to optimize performance by:
    - Avoiding redundant permission checks within a short time window
    - Providing quick responses for repeated permission queries
    - Reducing the overhead of AppleScript execution for permission testing
    
    Args:
        value: The automation permission status to cache:
               - True: Automation permissions are granted
               - False: Automation permissions are denied
               - None: Permission status is unknown/undetermined
    """
    global _AUTOMATION_PERMISSION_CACHE
    _AUTOMATION_PERMISSION_CACHE = (time.monotonic(), value)


def _read_automation_cache(force_refresh: bool = False) -> tuple[bool | None, bool]:
    """Read the automation permission status from the cache with TTL validation.
    
    This function retrieves the cached automation permission status if it's still
    valid (within the TTL window). It provides a way to avoid expensive permission
    checks when the status is already known and recent.
    
    The cache has a TTL (time-to-live) of AUTOMATION_PERMISSION_CACHE_TTL seconds
    to balance performance with accuracy, since permission status can change
    (e.g., user grants/revokes permissions).
    
    Args:
        force_refresh: If True, ignore cache and return (None, False) to force
                      a fresh permission check
        
    Returns:
        Tuple of (cached_value, cache_hit):
        - cached_value: The cached permission status (True/False/None) or None if cache miss
        - cache_hit: Boolean indicating whether a valid cached value was found
    """
    if force_refresh:
        return None, False
    cache = _AUTOMATION_PERMISSION_CACHE
    if cache is None:
        return None, False
    ts, value = cache
    if time.monotonic() - ts <= AUTOMATION_PERMISSION_CACHE_TTL:
        return value, True
    return None, False


def _automation_denied_from_stderr(stderr: str) -> bool:
    """Detect if AppleScript automation was denied based on stderr output.
    
    This function analyzes the stderr output from AppleScript execution to determine
    if the failure was due to automation permission denial. macOS returns specific
    error codes and messages when automation is not permitted, which this function
    recognizes.
    
    The function checks for several indicators of permission denial:
    - Error code -1743 (standard macOS automation denial error)
    - Various text patterns indicating permission issues
    - Localized error messages in different languages
    
    This detection is crucial for providing appropriate user feedback and avoiding
    repeated failed attempts when permissions are known to be denied.
    
    Args:
        stderr: The stderr output from AppleScript execution
        
    Returns:
        True if the stderr indicates automation permission was denied, False otherwise
    """
    if not stderr:
        return False
    if "-1743" in stderr:
        return True
    lowered = stderr.lower()
    return any(token in lowered for token in _AUTOMATION_DENIED_SUBSTRINGS)


def check_automation_permission_granted(force_refresh: bool = False) -> bool | None:
    """Check if AppleScript automation permissions are granted for browser applications.
    
    This function determines whether the system has been granted automation permissions
    to control browser applications via AppleScript. It's a critical check for the
    browser URL tracking functionality, as automation permissions are required to
    extract URLs from browsers.
    
    The function uses a multi-step approach:
    
    1. **Cache Check**: First checks if permission status is cached and still valid
       to avoid expensive repeated checks.
    
    2. **Browser Detection**: Scans for currently running browser applications that
       support automation.
    
    3. **Permission Testing**: Attempts to execute simple AppleScript commands on
       each running browser to test if automation is permitted.
    
    4. **Result Caching**: Caches the result to optimize future checks.
    
    The function handles various scenarios:
    - No browsers running: Returns None (unknown status)
    - All browsers deny automation: Returns False
    - At least one browser allows automation: Returns True
    - Mixed results: Returns None (inconclusive)
    
    This check is typically performed during system initialization to provide early
    feedback about permission issues and optimize subsequent browser URL queries.
    
    Args:
        force_refresh: If True, bypass cache and perform a fresh permission check
        
    Returns:
        - True: Automation permissions are granted (at least one browser allows it)
        - False: Automation permissions are denied (all browsers deny it)
        - None: Permission status is unknown (no browsers running or inconclusive results)
    """
    cached_value, cache_hit = _read_automation_cache(force_refresh)
    if cache_hit:
        return cached_value

    inspector = MacOSAppAndBrowserInspector(logging.getLogger("gum.automation_probe"))
    running = inspector.running_browser_applications()

    denied_detected = False
    attempted = False

    for app_name, key, bundle_id in running:
        attempted = True
        inspector.last_frontmost_bundle_id = bundle_id
        result = inspector._run_browser_scripts(app_name, key)
        if result is not None:
            return True

        cached_value, cache_hit = _read_automation_cache()
        if cache_hit and cached_value is False:
            denied_detected = True
            break

    if denied_detected:
        return False

    if attempted:
        _update_automation_cache(None)
    return None
