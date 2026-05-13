from __future__ import annotations
from typing import List, Dict, Optional, Iterable

import Quartz
from shapely.geometry import box
from shapely.ops import unary_union

from ._capture_base import CaptureBase

class CaptureMac(CaptureBase):
    """
    macOS-specific screen capture and window management using Quartz.
    """

    def _get_global_bounds(self) -> tuple[float, float, float, float]:
        """Return a bounding box enclosing **all** physical displays."""
        err, ids, cnt = Quartz.CGGetActiveDisplayList(16, None, None)
        if err != Quartz.kCGErrorSuccess:
            raise OSError(f"CGGetActiveDisplayList failed: {err}")

        min_x = min_y = float("inf")
        max_x = max_y = -float("inf")
        for did in ids[:cnt]:
            r = Quartz.CGDisplayBounds(did)
            x0, y0 = r.origin.x, r.origin.y
            x1, y1 = x0 + r.size.width, y0 + r.size.height
            min_x, min_y = min(min_x, x0), min(min_y, y0)
            max_x, max_y = max(max_x, x1), max(max_y, y1)
        return min_x, min_y, max_x, max_y

    def get_monitor_geometries(self) -> List[Dict[str, int]]:
        """Returns a list of monitor geometries using Quartz."""
        err, ids, cnt = Quartz.CGGetActiveDisplayList(16, None, None)
        if err != Quartz.kCGErrorSuccess:
            raise OSError(f"CGGetActiveDisplayList failed: {err}")

        monitors = []
        for did in ids[:cnt]:
            r = Quartz.CGDisplayBounds(did)
            monitors.append({
                "left": int(r.origin.x),
                "top": int(r.origin.y),
                "width": int(r.size.width),
                "height": int(r.size.height)
            })
        return monitors

    def get_window_list(self) -> List[Dict]:
        """List onscreen windows using Quartz."""
        opts = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListOptionIncludingWindow
        )
        wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
        
        result = []
        for info in wins:
            bounds = info.get("kCGWindowBounds", {})
            result.append({
                "owner_name": info.get("kCGWindowOwnerName", ""),
                "title": info.get("kCGWindowName", ""),
                "bounds": {
                    "X": bounds.get("X", 0),
                    "Y": bounds.get("Y", 0),
                    "Width": bounds.get("Width", 0),
                    "Height": bounds.get("Height", 0),
                },
                "is_visible": True # Since we use kCGWindowListOptionOnScreenOnly
            })
        return result

    def is_any_app_visible(self, app_names: List[str]) -> bool:
        """Determines app visibility using Quartz and Shapely for area calculation."""
        if not app_names:
            return False
            
        _, _, _, gmax_y = self._get_global_bounds()
        targets = set(app_names)

        opts = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListOptionIncludingWindow
        )
        wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)

        occupied = None
        for info in wins:
            owner = info.get("kCGWindowOwnerName", "")
            if owner in ("Dock", "WindowServer", "Window Server"):
                continue

            bounds = info.get("kCGWindowBounds", {})
            x, y, w, h = (
                bounds.get("X", 0),
                bounds.get("Y", 0),
                bounds.get("Width", 0),
                bounds.get("Height", 0),
            )
            if w <= 0 or h <= 0:
                continue

            inv_y = gmax_y - y - h
            poly = box(x, inv_y, x + w, inv_y + h)
            if poly.is_empty:
                continue

            visible = poly if occupied is None else poly.difference(occupied)
            if not visible.is_empty:
                if owner in targets:
                    return True # Found a visible window for one of the target apps
                occupied = poly if occupied is None else unary_union([occupied, poly])

        return False

    def get_monitor_at_point(self, x: float, y: float) -> Optional[Dict[str, int]]:
        """Finds the monitor geometry containing the point using Quartz bounds."""
        monitors = self.get_monitor_geometries()
        for m in monitors:
            if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
                return m
        return None
