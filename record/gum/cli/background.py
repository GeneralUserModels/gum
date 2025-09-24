from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from ..gum import gum as GumApp
from ..observers import AppAndBrowserInspector, Screen


class BackgroundRecorder:
    """Controller to run/stop the recorder in a background thread."""

    _thread: Optional[threading.Thread] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _stop_event: Optional[asyncio.Event] = None
    _running: bool = False
    _screen: Optional[Screen] = None

    @classmethod
    def is_running(cls) -> bool:
        return cls._running

    @classmethod
    def start(
        cls,
        user_name: str = "anonymous",
        data_directory: str = "~/Downloads/records",
        screenshots_dir: str = "~/Downloads/records/screenshots",
        debug: bool = False,
        scroll_debounce: float = 0.5,
        scroll_min_distance: float = 5.0,
        scroll_max_frequency: int = 10,
        scroll_session_timeout: float = 2.0,
    ) -> None:
        if cls._running:
            return

        cls._stop_event = asyncio.Event()
        cls._loop = asyncio.new_event_loop()

        async def _run():
            inspector_logger = logging.getLogger("gum.inspector.background")
            app_inspector = AppAndBrowserInspector(inspector_logger)
            screen_observer = Screen(
                screenshots_dir=screenshots_dir,
                debug=debug,
                keystroke_log_path=f"{data_directory}/keystrokes.log",
                keyboard_timeout=2.0,
                keyboard_sample_interval_sec=0.25,
                scroll_debounce_sec=scroll_debounce,
                scroll_min_distance=scroll_min_distance,
                scroll_max_frequency=scroll_max_frequency,
                scroll_session_timeout=scroll_session_timeout,
                app_inspector=app_inspector,
            )
            BackgroundRecorder._screen = screen_observer
            async with GumApp(
                user_name,
                screen_observer,
                data_directory=data_directory,
                app_and_browser_inspector=app_inspector,
            ):
                await cls._stop_event.wait()

        def _thread_target():
            assert cls._loop is not None
            asyncio.set_event_loop(cls._loop)
            try:
                cls._loop.run_until_complete(_run())
            finally:
                try:
                    pending = asyncio.all_tasks(loop=cls._loop)
                    for task in pending:
                        task.cancel()
                    cls._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except Exception:
                    pass
                cls._loop.stop()
                cls._loop.close()
                cls._loop = None
                cls._stop_event = None
                cls._running = False
                cls._screen = None

        cls._thread = threading.Thread(target=_thread_target, daemon=True)
        cls._running = True
        cls._thread.start()

    @classmethod
    def stop(cls) -> None:
        if not cls._running:
            return
        if cls._loop and cls._stop_event:
            def _set_event():
                assert cls._stop_event is not None
                cls._stop_event.set()
            try:
                cls._loop.call_soon_threadsafe(_set_event)
            except RuntimeError:
                pass
        if cls._thread and cls._thread.is_alive():
            cls._thread.join(timeout=5)
        cls._thread = None
        cls._running = False

    @classmethod
    def post_key_event(cls, token: str, event_type: str) -> None:
        """Forward a key token event from the main thread to the Screen observer."""
        if not cls._running or cls._loop is None or cls._screen is None:
            return

        async def _dispatch():
            try:
                await cls._screen.handle_key_token_event(token, event_type)
            except Exception:
                pass

        try:
            asyncio.run_coroutine_threadsafe(_dispatch(), cls._loop)
        except Exception:
            pass
