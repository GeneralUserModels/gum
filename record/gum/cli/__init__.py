"""Command-line interface utilities for the Gum recorder."""

from .background import BackgroundRecorder
from .main import main, _run_cli

__all__ = ["BackgroundRecorder", "main", "cli_main"]



def cli_main():
    import asyncio
    asyncio.run(_run_cli())
