from __future__ import annotations

import argparse
import asyncio
import logging

from dotenv import load_dotenv

from ..gum import gum as GumApp
from ..observers import AppAndBrowserInspector, Screen

load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GUM - A Python package with command-line interface")
    parser.add_argument("--user-name", "-u", type=str, default="anonymous", help="The user name to use")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")

    # Output directories
    parser.add_argument(
        "--data-directory",
        type=str,
        default="~/Downloads/records",
        help="Directory for database and logs (default: ~/Downloads/records)",
    )
    parser.add_argument(
        "--screenshots-dir",
        type=str,
        default="~/Downloads/records/screenshots",
        help="Directory to save screenshots (default: ~/Downloads/records/screenshots)",
    )

    # Scroll filtering options
    parser.add_argument(
        "--scroll-debounce",
        type=float,
        default=0.5,
        help="Minimum time between scroll events (seconds, default: 0.5)",
    )
    parser.add_argument(
        "--scroll-min-distance",
        type=float,
        default=5.0,
        help="Minimum scroll distance to log (pixels, default: 5.0)",
    )
    parser.add_argument(
        "--scroll-max-frequency",
        type=int,
        default=10,
        help="Maximum scroll events per second (default: 10)",
    )
    parser.add_argument(
        "--scroll-session-timeout",
        type=float,
        default=2.0,
        help="Scroll session timeout (seconds, default: 2.0)",
    )

    return parser.parse_args()


async def _run_cli() -> None:
    args = parse_args()
    print(f"User Name: {args.user_name}")

    inspector_logger = logging.getLogger("gum.inspector")
    app_inspector = AppAndBrowserInspector(inspector_logger)

    screen_observer = Screen(
        screenshots_dir=args.screenshots_dir,
        debug=args.debug,
        scroll_debounce_sec=args.scroll_debounce,
        scroll_min_distance=args.scroll_min_distance,
        scroll_max_frequency=args.scroll_max_frequency,
        scroll_session_timeout=args.scroll_session_timeout,
        app_inspector=app_inspector,
    )

    async with GumApp(
        args.user_name,
        screen_observer,
        data_directory=args.data_directory,
        app_and_browser_inspector=app_inspector,
    ):
        await asyncio.Future()


def main() -> None:
    asyncio.run(_run_cli())


if __name__ == "__main__":
    main()
