from __future__ import annotations

import asyncio
import contextlib
import math
from collections import deque


DEFAULT_SAMPLE_INTERVAL_SECONDS = 1.0
DEFAULT_RECENT_SAMPLE_COUNT = 120


class EventLoopLagMonitor:
    """Measure event-loop scheduling delay with fixed, bounded state."""

    def __init__(
        self,
        *,
        sample_interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
        recent_sample_count: int = DEFAULT_RECENT_SAMPLE_COUNT,
    ) -> None:
        interval = float(sample_interval_seconds)
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError('sample_interval_seconds must be greater than zero')
        sample_count = int(recent_sample_count)
        if sample_count < 2 or sample_count > 3600:
            raise ValueError('recent_sample_count must be between 2 and 3600')
        self.sample_interval_seconds = interval
        self.recent_sample_count = sample_count
        self._recent_lag_ms: deque[float] = deque(maxlen=sample_count)
        self._samples_total = 0
        self._max_lag_ms = 0.0
        self._last_lag_ms = 0.0
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start sampling on the current event loop; repeated calls are safe."""

        if self.running:
            return
        self._task = asyncio.create_task(
            self._run(),
            name='event-loop-lag-monitor',
        )

    async def stop(self) -> None:
        """Cancel and await the owned sampler task."""

        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        expected_at = loop.time() + self.sample_interval_seconds
        while True:
            await asyncio.sleep(max(expected_at - loop.time(), 0.0))
            observed_at = loop.time()
            self._record_lag_seconds(max(observed_at - expected_at, 0.0))
            # One observation captures a long stall; do not replay every
            # missed interval in a tight loop after the scheduler recovers.
            expected_at = observed_at + self.sample_interval_seconds

    def _record_lag_seconds(self, lag_seconds: float) -> None:
        lag_ms = max(float(lag_seconds), 0.0) * 1000
        self._last_lag_ms = lag_ms
        self._max_lag_ms = max(self._max_lag_ms, lag_ms)
        self._recent_lag_ms.append(lag_ms)
        self._samples_total += 1

    def snapshot(self) -> dict[str, int | float | bool]:
        """Return aggregate metrics without exposing task or tenant state."""

        recent = sorted(self._recent_lag_ms)
        if recent:
            p95_index = max(math.ceil(len(recent) * 0.95) - 1, 0)
            recent_p95_ms = recent[p95_index]
            recent_max_ms = recent[-1]
        else:
            recent_p95_ms = 0.0
            recent_max_ms = 0.0
        return {
            'running': self.running,
            'samples_total': self._samples_total,
            'last_lag_ms': self._last_lag_ms,
            'recent_p95_lag_ms': recent_p95_ms,
            'recent_max_lag_ms': recent_max_ms,
            'max_lag_ms': self._max_lag_ms,
        }
