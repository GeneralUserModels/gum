from __future__ import annotations
import ctypes
import ctypes.wintypes
import os
from typing import List, Dict, Optional

# --- Win32 API Constants and Structures ---
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

# Process Access Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szDevice", ctypes.wintypes.WCHAR * 32),
    ]

# --- DLL Loads ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
shcore = None
try:
    shcore = ctypes.windll.shcore
except (AttributeError, OSError):
    pass

# Set process DPI awareness to ensure physical coordinates
# 1 = PROCESS_SYSTEM_DPI_AWARE, 2 = PROCESS_PER_MONITOR_DPI_AWARE
try:
    if shcore and hasattr(shcore, 'SetProcessDpiAwareness'):
        shcore.SetProcessDpiAwareness(1)
    else:
        user32.SetProcessDPIAware()
except Exception:
    pass

from ._capture_base import CaptureBase

class CaptureWindows(CaptureBase):
    """
    Windows-specific screen capture and window management.
    """

    def _get_window_owner(self, hwnd: int) -> str:
        """Helper to get the process name (executable name) for a window handle."""
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        process_handle = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
        )
        if not process_handle:
            return ""

        buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        success = psapi.GetModuleFileNameExW(process_handle, 0, buffer, ctypes.sizeof(buffer))
        kernel32.CloseHandle(process_handle)
        
        if success:
            exe_path = buffer.value
            return os.path.splitext(os.path.basename(exe_path))[0]
        return ""

    def get_monitor_geometries(self) -> List[Dict[str, int]]:
        """Returns a list of monitor geometries using Win32 API."""
        monitors = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                monitors.append({
                    "left": int(info.rcMonitor.left),
                    "top": int(info.rcMonitor.top),
                    "width": int(info.rcMonitor.right - info.rcMonitor.left),
                    "height": int(info.rcMonitor.bottom - info.rcMonitor.top),
                })
            return True

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL,
            ctypes.wintypes.HMONITOR,
            ctypes.wintypes.HDC,
            ctypes.POINTER(RECT),
            ctypes.wintypes.LPARAM
        )
        
        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
        return monitors

    def is_any_app_visible(self, app_names: List[str]) -> bool:
        """Determines app visibility by enumerating onscreen windows."""
        if not app_names:
            return False
            
        targets = {name.lower() for name in app_names}
        found = [False] # Use a list to allow modification inside callback

        def callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            
            owner = self._get_window_owner(hwnd).lower()
            if owner in targets:
                rect = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                if (rect.right > rect.left) and (rect.bottom > rect.top):
                    found[0] = True
                    return False # Stop enumerating
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL,
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPARAM
        )
        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return found[0]

    def get_monitor_at_point(self, x: float, y: float) -> Optional[Dict[str, int]]:
        """Finds the monitor geometry containing the point using Win32 API."""
        point = ctypes.wintypes.POINT(int(x), int(y))
        hMonitor = user32.MonitorFromPoint(point, 0) # MONITOR_DEFAULTTONULL
        
        if hMonitor:
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                return {
                    "left": int(info.rcMonitor.left),
                    "top": int(info.rcMonitor.top),
                    "width": int(info.rcMonitor.right - info.rcMonitor.left),
                    "height": int(info.rcMonitor.bottom - info.rcMonitor.top),
                }
        return None

    def get_window_list(self) -> List[Dict]:
        """List onscreen windows using Win32 API."""
        windows = []

        def callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex_style & WS_EX_TOOLWINDOW:
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            
            windows.append({
                "owner_name": self._get_window_owner(hwnd),
                "title": title_buffer.value,
                "bounds": {
                    "X": rect.left,
                    "Y": rect.top,
                    "Width": rect.right - rect.left,
                    "Height": rect.bottom - rect.top,
                },
                "is_visible": True
            })
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL,
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPARAM
        )
        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return windows
