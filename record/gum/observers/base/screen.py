from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from PIL import Image, ImageDraw
from pynput import mouse

from .observer import Observer
from ..constants import (
    CAPTURE_FPS_DEFAULT,
    MEMORY_CLEANUP_INTERVAL_DEFAULT,
    MON_START_INDEX,
    KEYBOARD_TIMEOUT_DEFAULT,
    KEYBOARD_SAMPLE_INTERVAL_DEFAULT,
    SCROLL_DEBOUNCE_SEC_DEFAULT,
    SCROLL_MIN_DISTANCE_DEFAULT,
    SCROLL_MAX_FREQUENCY_DEFAULT,
    SCROLL_SESSION_TIMEOUT_DEFAULT,
)
from .keyboard import KeyDispatch, KeyboardBackend, NullKeyboardBackend
from .mouse import MouseBackend, NullMouseBackend
from .screenshots import ScreenshotBackend
from ...schemas import Update

VisibilityGuard = Callable[[Iterable[str]], bool]


class Screen(Observer):
    """Platform-agnostic core for observing screen, keyboard, and mouse activity."""

    _CAPTURE_FPS: int = CAPTURE_FPS_DEFAULT
    _PERIODIC_SEC: int = 30
    _DEBOUNCE_SEC: int = 1
    _MON_START: int = MON_START_INDEX
    _MEMORY_CLEANUP_INTERVAL: int = MEMORY_CLEANUP_INTERVAL_DEFAULT
    _MAX_WORKERS: int = 4

    _SCROLL_DEBOUNCE_SEC: float = SCROLL_DEBOUNCE_SEC_DEFAULT
    _SCROLL_MIN_DISTANCE: float = SCROLL_MIN_DISTANCE_DEFAULT
    _SCROLL_MAX_FREQUENCY: int = SCROLL_MAX_FREQUENCY_DEFAULT
    _SCROLL_SESSION_TIMEOUT: float = SCROLL_SESSION_TIMEOUT_DEFAULT

    def __init__(
        self,
        keyboard_backend: Optional[KeyboardBackend],
        mouse_backend: Optional[MouseBackend],
        screenshot_backend_factory: Callable[[], ScreenshotBackend],
        app_inspector: Optional[Any] = None,
        visibility_guard: Optional[VisibilityGuard] = None,
        *,
        screenshots_dir: str = "~/Downloads/records/screenshots",
        skip_when_visible: Optional[str | Sequence[str]] = None,
        history_k: int = 10,
        debug: bool = False,
        keyboard_timeout: float = KEYBOARD_TIMEOUT_DEFAULT,
        keystroke_log_path: Optional[str] = None,
        keyboard_sample_interval_sec: float = KEYBOARD_SAMPLE_INTERVAL_DEFAULT,
        scroll_debounce_sec: float = SCROLL_DEBOUNCE_SEC_DEFAULT,
        scroll_min_distance: float = SCROLL_MIN_DISTANCE_DEFAULT,
        scroll_max_frequency: int = SCROLL_MAX_FREQUENCY_DEFAULT,
        scroll_session_timeout: float = SCROLL_SESSION_TIMEOUT_DEFAULT,
    ) -> None:
        self._keyboard_backend = keyboard_backend or NullKeyboardBackend()
        self._mouse_backend = mouse_backend or NullMouseBackend()
        self._screenshot_backend_factory = screenshot_backend_factory
        self._app_inspector = app_inspector
        self._visibility_guard = visibility_guard

        self.screens_dir = os.path.abspath(os.path.expanduser(screenshots_dir))
        os.makedirs(self.screens_dir, exist_ok=True)

        if isinstance(skip_when_visible, str):
            self._guard = {skip_when_visible}
        else:
            self._guard = set(skip_when_visible or [])

        self.debug = debug
        self._thread_pool = ThreadPoolExecutor(max_workers=self._MAX_WORKERS)

        # Scroll filtering configuration
        self._scroll_debounce_sec = scroll_debounce_sec
        self._scroll_min_distance = scroll_min_distance
        self._scroll_max_frequency = scroll_max_frequency
        self._scroll_session_timeout = scroll_session_timeout

        # Frame buffers shared with worker
        self._frames: Dict[int, Any] = {}
        self._frame_lock = asyncio.Lock()

        self._history: deque[str] = deque(maxlen=max(0, history_k))
        self._pending_event: Optional[dict] = None
        self._debounce_handle: Optional[asyncio.TimerHandle] = None

        # keyboard activity tracking
        self._key_activity_start: Optional[float] = None
        self._key_activity_timeout: float = keyboard_timeout
        self._key_screenshots: List[str] = []
        self._key_activity_lock = asyncio.Lock()
        self._last_key_screenshot_time: Optional[float] = None
        self._last_key_position: Optional[tuple[float, float, int]] = None
        self._keystroke_log_path: Optional[str] = (
            os.path.abspath(os.path.expanduser(keystroke_log_path)) if keystroke_log_path else None
        )
        self._keyboard_sample_interval_sec: float = max(0.0, float(keyboard_sample_interval_sec))

        # scroll activity tracking
        self._scroll_last_time: Optional[float] = None
        self._scroll_last_position: Optional[tuple[float, float]] = None
        self._scroll_session_start: Optional[float] = None
        self._scroll_event_count: int = 0
        self._scroll_lock = asyncio.Lock()

        # Keyboard backend bookkeeping
        self._keyboard_dispatch: Optional[KeyDispatch] = None

        # Mouse backend bookkeeping
        self._mouse_started: bool = False

        super().__init__()

        if self._detect_high_dpi():
            self._CAPTURE_FPS = 3
            self._MEMORY_CLEANUP_INTERVAL = 20
            if self.debug:
                logging.getLogger("Screen").info("High-DPI display detected, using conservative settings")

    @staticmethod
    def _mon_for(x: float, y: float, mons: Sequence[dict]) -> Optional[int]:
        for idx, m in enumerate(mons, 1):
            if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
                return idx
        return 1

    async def _run_in_thread(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._thread_pool, lambda: func(*args, **kwargs))

    def _detect_high_dpi(self) -> bool:
        try:
            backend = self._screenshot_backend_factory()
            with backend as sct:
                for monitor in sct.monitors[self._MON_START:]:
                    if monitor.get("width", 0) > 2560 or monitor.get("height", 0) > 1600:
                        return True
        except Exception:
            return False
        return False

    def _should_log_scroll(self, x: float, y: float, dx: float, dy: float) -> bool:
        current_time = time.time()

        if (
            self._scroll_session_start is None
            or current_time - self._scroll_session_start > self._scroll_session_timeout
        ):
            self._scroll_session_start = current_time
            self._scroll_event_count = 0
            self._scroll_last_position = (x, y)
            self._scroll_last_time = current_time
            return True

        if self._scroll_last_time is not None and current_time - self._scroll_last_time < self._scroll_debounce_sec:
            return False

        if self._scroll_last_position is not None:
            distance = ((x - self._scroll_last_position[0]) ** 2 + (y - self._scroll_last_position[1]) ** 2) ** 0.5
            if distance < self._scroll_min_distance:
                return False

        self._scroll_event_count += 1
        session_duration = current_time - self._scroll_session_start
        if session_duration > 0:
            frequency = self._scroll_event_count / session_duration
            if frequency > self._scroll_max_frequency:
                return False

        self._scroll_last_position = (x, y)
        self._scroll_last_time = current_time
        return True

    def _snapshot_app_context(self, cursor: Optional[tuple[float, float]] = None) -> tuple[Optional[str], Optional[str]]:
        inspector = getattr(self, "_app_inspector", None)
        if inspector is None:
            return None, None
        app_name: Optional[str] = None
        browser_url: Optional[str] = None

        try:
            app_name = inspector.get_frontmost_app_name()
        except Exception:
            app_name = None

        if not app_name and cursor and hasattr(inspector, "app_at_point"):
            try:
                name_at_point, _ = inspector.app_at_point(*cursor)
            except Exception:
                name_at_point = None
            if name_at_point:
                app_name = name_at_point

        if app_name:
            try:
                browser_url = inspector.get_browser_url(app_name)
            except Exception:
                browser_url = None

        return app_name, browser_url

    async def _cleanup_key_screenshots(self) -> None:
        if len(self._key_screenshots) <= 2:
            return
        to_delete = self._key_screenshots[1:-1]
        self._key_screenshots = [self._key_screenshots[0], self._key_screenshots[-1]]

        for path in to_delete:
            try:
                await self._run_in_thread(os.remove, path)
                if self.debug:
                    logging.getLogger("Screen").info(f"Deleted intermediate screenshot: {path}")
            except OSError:
                pass

    async def _save_frame(
        self,
        frame,
        x: float,
        y: float,
        tag: str,
        box_color: str = "red",
        box_width: int = 10,
        scale: float = 1.0,
    ) -> str:
        ts = f"{time.time():.5f}"
        path = os.path.join(self.screens_dir, f"{ts}_{tag}.jpg")
        image = Image.frombytes("RGB", (frame.width, frame.height), frame.rgb)
        draw = ImageDraw.Draw(image)
        sx = max(1.0, float(scale))
        x = int(x * sx)
        y = int(y * sx)
        x1, x2 = max(0, x - 30), min(frame.width, x + 30)
        y1, y2 = max(0, y - 20), min(frame.height, y + 20)
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=box_width)

        await self._run_in_thread(
            image.save,
            path,
            "JPEG",
            quality=70,
            optimize=True,
        )

        del draw
        del image
        return path

    async def _process_and_emit(
        self,
        before_path: str,
        after_path: str | None,
        action: Optional[str],
        ev: Optional[dict],
    ) -> None:
        if ev is None:
            return
        cursor = ev.get("cursor") if isinstance(ev, dict) else None
        app_name, browser_url = self._snapshot_app_context(cursor)
        mon = ev.get("mon") if isinstance(ev, dict) else None
        mon_sfx = f"@mon{mon}" if mon is not None else ""
        if action and "scroll" in action:
            scroll_info = ev.get("scroll", (0, 0))
            step = f"scroll{mon_sfx}({ev['position'][0]:.1f}, {ev['position'][1]:.1f}, dx={scroll_info[0]:.2f}, dy={scroll_info[1]:.2f})"
            await self.update_queue.put(
                Update(content=step, content_type="input_text", app_name=app_name, browser_url=browser_url)
            )
        elif action and "click" in action:
            step = f"{action}{mon_sfx}({ev['position'][0]:.1f}, {ev['position'][1]:.1f})"
            await self.update_queue.put(
                Update(content=step, content_type="input_text", app_name=app_name, browser_url=browser_url)
            )
        elif action:
            step = f"{action}{mon_sfx}({ev.get('text', '')})"
            await self.update_queue.put(
                Update(content=step, content_type="input_text", app_name=app_name, browser_url=browser_url)
            )

    async def stop(self) -> None:
        await super().stop()
        try:
            self._keyboard_backend.stop()
        except Exception:
            pass
        try:
            self._mouse_backend.stop()
        except Exception:
            pass

        async with self._frame_lock:
            for frame in self._frames.values():
                if frame is not None:
                    del frame
            self._frames.clear()
        await self._run_in_thread(gc.collect)
        self._thread_pool.shutdown(wait=True)

    def _skip(self) -> bool:
        if not self._guard or self._visibility_guard is None:
            return False
        try:
            return self._visibility_guard(self._guard)
        except Exception:
            return False

    async def _worker(self) -> None:
        log = logging.getLogger("Screen")
        if self.debug:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [Screen] %(message)s",
                datefmt="%H:%M:%S",
            )
        else:
            log.addHandler(logging.NullHandler())
            log.propagate = False

        cap_fps = self._CAPTURE_FPS
        loop = asyncio.get_running_loop()

        with self._screenshot_backend_factory() as capture:
            mons = capture.monitors[self._MON_START:]

            async def flush_pending() -> None:
                if self._pending_event is None:
                    return
                if self._skip():
                    self._pending_event = None
                    return

                ev = self._pending_event
                mon = mons[ev["mon"] - 1]
                try:
                    aft = await self._run_in_thread(capture.grab, mon)
                except Exception as e:
                    if self.debug:
                        log.error(f"Failed to capture after frame: {e}")
                    self._pending_event = None
                    return

                try:
                    scale = float(aft.width) / float(mon.get("width", aft.width) or aft.width)
                    if scale <= 0:
                        scale = 1.0
                except Exception:
                    scale = 1.0

                bef_path = await self._save_frame(
                    ev["before"],
                    ev["position"][0],
                    ev["position"][1],
                    f"{ev['type']}_before@mon{ev['mon']}",
                    scale=scale,
                )
                aft_path = await self._save_frame(
                    aft,
                    ev["position"][0],
                    ev["position"][1],
                    f"{ev['type']}_after@mon{ev['mon']}",
                    scale=scale,
                )
                await self._process_and_emit(bef_path, aft_path, ev["type"], ev)
                log.info(f"{ev['type']} captured on monitor {ev['mon']}")
                self._pending_event = None

            async def scroll_event(x: float, y: float, dx: float, dy: float):
                async with self._scroll_lock:
                    if not self._should_log_scroll(x, y, dx, dy):
                        if self.debug:
                            log.info(f"Scroll filtered out: dx={dx:.2f}, dy={dy:.2f}")
                        return
                idx = self._mon_for(x, y, mons)
                if idx is None:
                    return
                mon = mons[idx - 1]
                x_local = x - mon["left"]
                y_local = y - mon["top"]
                log.info(
                    f"scroll @({x_local:7.1f},{y_local:7.1f}) dx={dx:.2f} dy={dy:.2f} → mon={idx}"
                )
                scroll_magnitude = (dx ** 2 + dy ** 2) ** 0.5
                if scroll_magnitude < 1.0:
                    if self.debug:
                        log.info(f"Scroll too small: magnitude={scroll_magnitude:.2f}")
                    return
                if self._skip():
                    return
                async with self._frame_lock:
                    fr = self._frames.get(idx)
                if fr is None:
                    return
                try:
                    scale = float(fr.width) / float(mon.get("width", fr.width) or fr.width)
                    if scale <= 0:
                        scale = 1.0
                except Exception:
                    scale = 1.0

                self._pending_event = {
                    "type": "scroll",
                    "position": (x_local, y_local),
                    "mon": idx,
                    "before": fr,
                    "scale": scale,
                    "scroll": (dx, dy),
                    "cursor": (x, y),
                }
                await flush_pending()

            async def mouse_event(x: float, y: float, typ: str):
                idx = self._mon_for(x, y, mons)
                if idx is None:
                    return
                mon = mons[idx - 1]
                x_local = x - mon["left"]
                y_local = y - mon["top"]
                log.info(
                    f"{typ:<6} @({x_local:7.1f},{y_local:7.1f}) → mon={idx}   {'(guarded)' if self._skip() else ''}"
                )
                if self._skip():
                    return
                async with self._frame_lock:
                    fr = self._frames.get(idx)
                if fr is None:
                    return
                try:
                    scale = float(fr.width) / float(mon.get("width", fr.width) or fr.width)
                    if scale <= 0:
                        scale = 1.0
                except Exception:
                    scale = 1.0

                self._pending_event = {
                    "type": typ,
                    "position": (x_local, y_local),
                    "mon": idx,
                    "before": fr,
                    "scale": scale,
                    "cursor": (x, y),
                }
                await flush_pending()

            def schedule_mouse_click(x: float, y: float, typ: str) -> None:
                asyncio.run_coroutine_threadsafe(mouse_event(x, y, typ), loop)

            def schedule_mouse_scroll(x: float, y: float, dx: float, dy: float) -> None:
                asyncio.run_coroutine_threadsafe(scroll_event(x, y, dx, dy), loop)

            try:
                self._mouse_backend.start(schedule_mouse_click, schedule_mouse_scroll)
                self._mouse_started = True
            except Exception as exc:
                self._mouse_started = False
                log.warning(f"Failed to start mouse backend: {exc}")

            async def key_token_event(tok: str, typ: str):
                controller = mouse.Controller()
                x, y = controller.position
                idx = self._mon_for(x, y, mons)
                if idx is None:
                    return
                mon = mons[idx - self._MON_START]
                x_local = x - mon["left"]
                y_local = y - mon["top"]
                if self._keystroke_log_path:
                    try:
                        os.makedirs(os.path.dirname(self._keystroke_log_path), exist_ok=True)
                        with open(self._keystroke_log_path, "a") as f:
                            f.write(f"{datetime.now().isoformat()}\t{typ}\t{tok}\n")
                    except Exception:
                        pass

                step = f"key_{typ}@mon{idx}({tok})"
                app_name, browser_url = self._snapshot_app_context((x, y))
                await self.update_queue.put(
                    Update(
                        content=step,
                        content_type="input_text",
                        app_name=app_name,
                        browser_url=browser_url,
                    )
                )

                async with self._key_activity_lock:
                    current_time = time.time()
                    try:
                        async with self._frame_lock:
                            fr = self._frames.get(idx)
                        scale = float(fr.width) / float(mon.get("width", fr.width) or fr.width) if fr else 1.0
                    except Exception:
                        scale = 1.0

                    if (
                        self._key_activity_start is None
                        or current_time - self._key_activity_start > self._key_activity_timeout
                    ):
                        self._key_activity_start = current_time
                        self._key_screenshots = []
                        if fr is not None:
                            screenshot_path = await self._save_frame(fr, x_local, y_local, f"{step}_first", scale=scale)
                            self._key_screenshots.append(screenshot_path)
                        self._last_key_screenshot_time = current_time
                        self._last_key_position = (x_local, y_local, idx)
                    else:
                        should_sample = (
                            self._last_key_screenshot_time is None
                            or (current_time - self._last_key_screenshot_time) >= self._keyboard_sample_interval_sec
                        )
                        if should_sample and fr is not None:
                            screenshot_path = await self._save_frame(fr, x_local, y_local, f"{step}_intermediate", scale=scale)
                            self._key_screenshots.append(screenshot_path)
                            self._last_key_screenshot_time = current_time
                            self._last_key_position = (x_local, y_local, idx)

                    if len(self._key_screenshots) > 2:
                        asyncio.create_task(self._cleanup_key_screenshots())

            async def _handle_key_token_event(tok: str, typ: str):
                await key_token_event(tok, typ)

            self.handle_key_token_event = _handle_key_token_event  # type: ignore[attr-defined]

            def schedule_key_token_event(tok: str, typ: str) -> None:
                asyncio.run_coroutine_threadsafe(key_token_event(tok, typ), loop)

            # a bit hacky, but this helps us run the keyboard in the main thread when running the app
            # (otherwise, on macOS running in the background will crash...)
            disable_keyboard_env = os.environ.get("GUM_DISABLE_KEYBOARD", "").strip() == "1"
            if not disable_keyboard_env:
                try:
                    self._keyboard_backend.start(schedule_key_token_event)
                except Exception as exc:
                    log.warning(f"Keyboard backend unavailable: {exc}")
            else:
                log.info("Keyboard backend disabled via GUM_DISABLE_KEYBOARD=1; using main-thread shim events only")

            log.info(f"Screen observer started — guarding {self._guard or '∅'}")
            frame_count = 0

            while self._running:
                t0 = time.time()

                for idx, mon in enumerate(mons, 1):
                    old_frame = None
                    async with self._frame_lock:
                        old_frame = self._frames.get(idx)
                    try:
                        frame = await self._run_in_thread(capture.grab, mon)
                    except Exception as e:
                        if self.debug:
                            log.error(f"Failed to capture frame: {e}")
                        continue

                    async with self._frame_lock:
                        self._frames[idx] = frame

                    if old_frame is not None:
                        del old_frame

                    frame_count += 1
                    if frame_count % self._MEMORY_CLEANUP_INTERVAL == 0:
                        await self._run_in_thread(gc.collect)

                current_time = time.time()
                if (
                    self._key_activity_start is not None
                    and current_time - self._key_activity_start > self._key_activity_timeout
                    and len(self._key_screenshots) >= 1
                ):
                    async with self._key_activity_lock:
                        try:
                            if self._last_key_position is not None:
                                lx, ly, lidx = self._last_key_position
                                mon = mons[lidx - self._MON_START]
                                async with self._frame_lock:
                                    fr = self._frames.get(lidx)
                                scale = (
                                    float(fr.width) / float(mon.get("width", fr.width) or fr.width)
                                    if fr
                                    else 1.0
                                )
                                if fr is not None:
                                    final_path = await self._save_frame(fr, lx, ly, f"key_final@mon{lidx}", scale=scale)
                                    self._key_screenshots.append(final_path)
                        except Exception:
                            pass
                        await self._cleanup_key_screenshots()
                        self._key_activity_start = None
                        self._key_screenshots = []
                        self._last_key_screenshot_time = None
                        self._last_key_position = None

                dt = time.time() - t0
                await asyncio.sleep(max(0, (1 / cap_fps) - dt))

            try:
                await flush_pending()
            finally:
                try:
                    self._keyboard_backend.stop()
                except Exception:
                    pass
                try:
                    self._mouse_backend.stop()
                except Exception:
                    pass

                if self._key_activity_start is not None and len(self._key_screenshots) > 1:
                    async with self._key_activity_lock:
                        last_path = self._key_screenshots[-1]
                        final_path = last_path.replace("_intermediate", "_final")
                        try:
                            await self._run_in_thread(os.rename, last_path, final_path)
                            log.info(f"Final keyboard session cleanup, renamed: {final_path}")
                        except OSError:
                            pass
                        await self._cleanup_key_screenshots()
