"""Worker liveness is proven by active RPC, never by business traffic volume."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable


async def supervise_liveness(worker_task: asyncio.Task, watch: Awaitable[None]):
    """Fence the attempt: stop its process before surfacing watchdog failure."""
    watchdog_task = asyncio.ensure_future(watch)
    try:
        done, _ = await asyncio.wait(
            {worker_task, watchdog_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if worker_task in done:
            return await worker_task
        await watchdog_task
    finally:
        for task in (worker_task, watchdog_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(worker_task, watchdog_task, return_exceptions=True)


class WorkerWatchdog:
    def __init__(self, timeout_seconds: float = 90):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.timeout_seconds = timeout_seconds
        self.failed_since: float | None = None
        self.last_success: float | None = None
        self.failures = 0

    def observe(self, success: bool, *, now: float) -> bool:
        if success:
            self.failed_since = None
            self.last_success = now
            self.failures = 0
            return False
        self.failures += 1
        if self.failed_since is None:
            self.failed_since = now
        return now - self.failed_since >= self.timeout_seconds

    async def watch(
        self,
        probe: Callable[[], Awaitable[object]],
        *,
        interval: float = 15,
        probe_timeout: float = 10,
    ) -> None:
        while True:
            probe_task = asyncio.ensure_future(probe())
            try:
                done, _ = await asyncio.wait({probe_task}, timeout=probe_timeout)
                success = False
                if probe_task in done:
                    await probe_task
                    success = True
            except Exception:
                success = False
            finally:
                if not probe_task.done():
                    probe_task.cancel()
                await asyncio.gather(probe_task, return_exceptions=True)
            if self.observe(success, now=asyncio.get_running_loop().time()):
                raise TimeoutError(
                    "plugin worker unresponsive beyond watchdog threshold"
                )
            await asyncio.sleep(interval)
