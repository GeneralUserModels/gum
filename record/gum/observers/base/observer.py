from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import asyncio

class Observer(ABC):

    def __init__(self, name: Optional[str] = None) -> None:
        self.update_queue = asyncio.Queue()
        self._name = name or self.__class__.__name__

        self._running = True
        self._task: asyncio.Task | None = asyncio.create_task(self._worker_wrapper())

    @abstractmethod
    async def _worker(self) -> None:
        pass

    async def _worker_wrapper(self) -> None:
        try:
            await self._worker()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            raise
        finally:
            self._running = False

    # ─────────────────────────────── public API
    @property
    def name(self) -> str:
        return self._name

    async def get_update(self):
        """Return an Update if immediately available, else None (non-blocking)."""
        try:
            return self.update_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def stop(self) -> None:
        """Cancel the worker task and drain the queue."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # unblock any awaiters
        while not self.update_queue.empty():
            self.update_queue.get_nowait()
