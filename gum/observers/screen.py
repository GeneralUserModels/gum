from __future__ import annotations
###############################################################################
# Imports                                                                     #
###############################################################################

# — Standard library —
import base64
import logging
import os
import time
import platform
from collections import deque
from typing import Any, Dict, Iterable, List, Optional

import asyncio

# — Third-party —
import mss
from PIL import Image
from pynput import mouse           # still synchronous

# — Local —
from .observer import Observer
from ..schemas import Update

# — OpenAI async client —
from openai import AsyncOpenAI

# — Local —
from gum.prompts.screen import TRANSCRIPTION_PROMPT, SUMMARY_PROMPT

###############################################################################
# Screen observer                                                             #
###############################################################################

class Screen(Observer):
    """Observer that captures and analyzes screen content around user interactions.

    This observer captures screenshots before and after user interactions (mouse movements,
    clicks, and scrolls) and uses GPT-4 Vision to analyze the content. It can also take
    periodic screenshots and skip captures when certain applications are visible.

    Args:
        screenshots_dir (str, optional): Directory to store screenshots. Defaults to "~/.cache/gum/screenshots".
        skip_when_visible (Optional[str | list[str]], optional): Application names to skip when visible.
            Defaults to None.
        transcription_prompt (Optional[str], optional): Custom prompt for transcribing screenshots.
            Defaults to None.
        summary_prompt (Optional[str], optional): Custom prompt for summarizing screenshots.
            Defaults to None.
        model_name (str, optional): GPT model to use for vision analysis. Defaults to "gpt-4o-mini".
        history_k (int, optional): Number of recent screenshots to keep in history. Defaults to 10.
        debug (bool, optional): Enable debug logging. Defaults to False.

    Attributes:
        _CAPTURE_FPS (int): Frames per second for screen capture.
        _DEBOUNCE_SEC (int): Seconds to wait before processing an interaction.
    """

    _CAPTURE_FPS: int = 10
    _DEBOUNCE_SEC: int = int(os.getenv("DEBOUNCE_SEC", "2"))

    # ─────────────────────────────── construction
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        screenshots_dir: str = "~/.cache/gum/screenshots",
        skip_when_visible: Optional[str | list[str]] = None,
        transcription_prompt: Optional[str] = None,
        summary_prompt: Optional[str] = None,
        history_k: int = 10,
        debug: bool = False,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        """Initialize the Screen observer."""
        self.screens_dir = os.path.abspath(os.path.expanduser(screenshots_dir))
        os.makedirs(self.screens_dir, exist_ok=True)

        self._guard = {skip_when_visible} if isinstance(skip_when_visible, str) else set(skip_when_visible or [])

        self.transcription_prompt = transcription_prompt or TRANSCRIPTION_PROMPT
        self.summary_prompt = summary_prompt or SUMMARY_PROMPT
        self.model_name = model_name

        self.debug = debug

        # platform-specific capture logic
        if platform.system() == "Darwin":
            from ._capture_mac import CaptureMac
            self.capture = CaptureMac()
        elif platform.system() == "Windows":
            from ._capture_windows import CaptureWindows
            self.capture = CaptureWindows()
        else:
            raise OSError(f"Unsupported platform: {platform.system()}")

        # state shared with worker
        self._frames: Dict[int, Any] = {}
        self._frame_lock = asyncio.Lock()

        self._history: deque[str] = deque(maxlen=max(0, history_k))
        self._pending_event: Optional[dict] = None
        self._debounce_handle: Optional[asyncio.TimerHandle] = None
        self.client = AsyncOpenAI(
            base_url=api_base or os.getenv("SCREEN_LM_API_BASE") or os.getenv("GUM_LM_API_BASE"), 
            api_key=api_key or os.getenv("SCREEN_LM_API_KEY") or os.getenv("GUM_LM_API_KEY") or os.getenv("OPENAI_API_KEY") or "None"
        )

        # call parent
        super().__init__()

    # ─────────────────────────────── tiny sync helpers
    @staticmethod
    def _encode_image(img_path: str) -> str:
        """Encode an image file as base64."""
        with open(img_path, "rb") as fh:
            return base64.b64encode(fh.read()).decode()

    # ─────────────────────────────── OpenAI Vision (async)
    async def _call_gpt_vision(self, prompt: str, img_paths: list[str]) -> str:
        """Call GPT Vision API to analyze images."""
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
            }
            for encoded in (await asyncio.gather(
                *[asyncio.to_thread(self._encode_image, p) for p in img_paths]
            ))
        ]
        content.append({"type": "text", "text": prompt})

        rsp = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": content}],
            response_format={"type": "text"},
        )
        return rsp.choices[0].message.content

    # ─────────────────────────────── I/O helpers
    async def _save_frame(self, frame, tag: str) -> str:
        """Save a frame as a JPEG image."""
        ts   = f"{time.time():.5f}"
        path = os.path.join(self.screens_dir, f"{ts}_{tag}.jpg")
        await asyncio.to_thread(
            Image.frombytes("RGB", (frame.width, frame.height), frame.rgb).save,
            path,
            "JPEG",
            quality=70,
        )
        return path

    async def _process_and_emit(self, before_path: str, after_path: str) -> None:
        """Process screenshots and emit an update."""
        self._history.append(before_path)
        prev_paths = list(self._history)

        try:
            transcription = await self._call_gpt_vision(self.transcription_prompt, [before_path, after_path])
        except Exception as exc:
            transcription = f"[transcription failed: {exc}]"

        prev_paths.append(before_path)
        prev_paths.append(after_path)
        try:
            summary = await self._call_gpt_vision(self.summary_prompt, prev_paths)
        except Exception as exc:
            summary = f"[summary failed: {exc}]"

        txt = (transcription + summary).strip()
        await self.update_queue.put(Update(content=txt, content_type="input_text"))

    # ─────────────────────────────── skip guard
    def _skip(self) -> bool:
        """Check if capture should be skipped based on visible applications."""
        return self.capture.is_any_app_visible(list(self._guard)) if self._guard else False

    # ─────────────────────────────── main async worker
    async def _worker(self) -> None:
        """Main worker method that captures and processes screenshots."""
        log = logging.getLogger("Screen")
        if self.debug:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [Screen] %(message)s", datefmt="%H:%M:%S")
        else:
            log.addHandler(logging.NullHandler())
            log.propagate = False

        CAP_FPS  = self._CAPTURE_FPS
        DEBOUNCE = self._DEBOUNCE_SEC

        loop = asyncio.get_running_loop()

        with mss.mss() as sct:
            mons = sct.monitors[1:] # mss 1-based index for real displays

            def schedule_event(x: float, y: float, typ: str):
                asyncio.run_coroutine_threadsafe(mouse_event(x, y, typ), loop)

            listener = mouse.Listener(
                on_move=lambda x, y: schedule_event(x, y, "move"),
                on_click=lambda x, y, btn, prs: schedule_event(x, y, "click") if prs else None,
                on_scroll=lambda x, y, dx, dy: schedule_event(x, y, "scroll"),
            )
            listener.start()

            async def flush():
                if self._pending_event is None:
                    return
                if self._skip():
                    self._pending_event = None
                    return

                ev = self._pending_event
                
                try:
                    # mss.grab is fast enough to run in-thread (~10ms) and avoid thread-local storage issues
                    aft = sct.grab(mons[ev["mon_idx"]])
                    bef_path = await self._save_frame(ev["before"], "before")
                    aft_path = await self._save_frame(aft, "after")
                    await self._process_and_emit(bef_path, aft_path)
                    log.info(f"{ev['type']} captured on monitor {ev['mon_idx']}")
                except Exception as exc:
                    log.debug(f"Failed to capture or process interaction: {exc}")
                finally:
                    self._pending_event = None

            def debounce_flush():
                asyncio.create_task(flush())

            async def mouse_event(x: float, y: float, typ: str):
                mon_geo = self.capture.get_monitor_at_point(x, y)
                log.info(
                    f"{typ:<6} @({x:7.1f},{y:7.1f}) → mon={mon_geo}   {'(guarded)' if self._skip() else ''}"
                )
                if self._skip() or mon_geo is None:
                    return

                # Find which mss monitor this corresponds to
                mon_idx = None
                for i, m in enumerate(mons):
                    if m["left"] == mon_geo["left"] and m["top"] == mon_geo["top"]:
                        mon_idx = i
                        break
                
                if mon_idx is None:
                    return

                if self._pending_event is None:
                    async with self._frame_lock:
                        bf = self._frames.get(mon_idx)
                    if bf is None:
                        return
                    self._pending_event = {"type": typ, "mon_idx": mon_idx, "before": bf}

                if self._debounce_handle:
                    self._debounce_handle.cancel()
                self._debounce_handle = loop.call_later(DEBOUNCE, debounce_flush)

            log.info(f"Screen observer started — guarding {self._guard or '∅'}")

            while self._running:
                t0 = time.time()

                for idx, m in enumerate(mons):
                    try:
                        # mss.grab is fast enough to run in-thread (~10ms) and avoid thread-local storage issues
                        frame = sct.grab(m)
                        async with self._frame_lock:
                            self._frames[idx] = frame
                    except Exception as exc:
                        log.debug(f"Main capture loop failed for monitor {idx}: {exc}")

                dt = time.time() - t0
                await asyncio.sleep(max(0, (1 / CAP_FPS) - dt))

            listener.stop()
            if self._debounce_handle:
                self._debounce_handle.cancel()
