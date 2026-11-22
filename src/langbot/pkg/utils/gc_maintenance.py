from __future__ import annotations

import asyncio
import contextlib
import gc
import math
import time
import typing


# Freezing is off by default: Core periodically replaces large startup
# structures (model catalog snapshots, bot/pipeline reloads). Frozen objects that
# later become cyclic garbage are never reclaimed, which on Cloud grew RSS by
# ~290 MiB/h and left an unfrozen heap that made each full collection take >1 s.
DEFAULT_FREEZE_AFTER_SECONDS = 0.0
DEFAULT_COLLECT_INTERVAL_SECONDS = 1800.0
SLOW_COLLECTION_LOG_SECONDS = 0.5


class GarbageCollectionMaintainer:
    """Keep cyclic garbage bounded in a long-running process with a large heap.

    CPython only runs a full (generation 2) collection after the objects
    promoted since the previous full collection reach 25% of all long-lived
    objects. A shared Core keeps tens of millions of long-lived objects (model
    catalogs, bots, pipelines), so full collections become rare while
    reconnecting platform adapters keep producing cyclic garbage: every closed
    TLS connection leaves an ``SSLProtocol``/transport/``SSLContext`` cycle of
    several hundred KiB that reference counting cannot free.

    The maintainer runs a full collection on a fixed interval so that garbage
    stays bounded. Optionally it can first freeze the heap once startup has
    settled (``freeze_after_seconds``), which moves those objects to the
    permanent generation so collections no longer traverse them. Freezing is
    off by default: objects frozen at startup that later become cyclic garbage
    (for example a replaced model catalog snapshot) are never reclaimed, and
    Core replaces such structures continuously, so the frozen heap leaks.
    """

    def __init__(
        self,
        *,
        freeze_after_seconds: float = DEFAULT_FREEZE_AFTER_SECONDS,
        collect_interval_seconds: float = DEFAULT_COLLECT_INTERVAL_SECONDS,
        logger: typing.Any = None,
        collect: typing.Callable[[int], int] = gc.collect,
        freeze: typing.Callable[[], None] = gc.freeze,
        freeze_count: typing.Callable[[], int] = gc.get_freeze_count,
    ) -> None:
        self.freeze_after_seconds = self._non_negative(freeze_after_seconds, 'freeze_after_seconds')
        self.collect_interval_seconds = self._non_negative(collect_interval_seconds, 'collect_interval_seconds')
        self._logger = logger
        self._collect = collect
        self._freeze = freeze
        self._freeze_count = freeze_count
        self._task: asyncio.Task[None] | None = None
        self._frozen = False
        self._collections_total = 0
        self._collected_total = 0
        self._last_collected = 0
        self._last_duration_ms = 0.0
        self._max_duration_ms = 0.0

    @staticmethod
    def _non_negative(value: typing.Any, name: str) -> float:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f'{name} must be a finite number >= 0')
        return number

    @property
    def enabled(self) -> bool:
        return self.freeze_after_seconds > 0 or self.collect_interval_seconds > 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start maintenance on the current event loop; repeated calls are safe."""

        if self.running or not self.enabled:
            return
        self._task = asyncio.create_task(self._run(), name='gc-maintenance')

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def freeze_once(self) -> int:
        """Collect, then move every surviving tracked object to the permanent generation."""

        self.collect_once()
        self._freeze()
        self._frozen = True
        return self._freeze_count()

    def collect_once(self) -> int:
        started = time.perf_counter()
        collected = int(self._collect(2))
        duration_ms = (time.perf_counter() - started) * 1000
        self._collections_total += 1
        self._collected_total += collected
        self._last_collected = collected
        self._last_duration_ms = duration_ms
        self._max_duration_ms = max(self._max_duration_ms, duration_ms)
        if duration_ms >= SLOW_COLLECTION_LOG_SECONDS * 1000:
            self._log('warning', f'Full garbage collection took {duration_ms:.0f} ms (collected {collected} objects)')
        return collected

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        if self.freeze_after_seconds > 0:
            await asyncio.sleep(self.freeze_after_seconds)
            frozen = self.freeze_once()
            self._log(
                'info',
                f'Froze {frozen} startup objects out of cyclic garbage collection '
                f'({loop.time() - started_at:.0f}s after start)',
            )
        if self.collect_interval_seconds <= 0:
            return
        while True:
            await asyncio.sleep(self.collect_interval_seconds)
            try:
                self.collect_once()
            except Exception as exc:  # pragma: no cover - gc.collect does not raise in practice
                self._log('warning', f'Periodic garbage collection failed: {exc}')

    def _log(self, level: str, message: str) -> None:
        if self._logger is None:
            return
        with contextlib.suppress(Exception):
            getattr(self._logger, level)(message)

    def snapshot(self) -> dict[str, typing.Any]:
        return {
            'running': self.running,
            'frozen': self._frozen,
            'frozen_objects': self._freeze_count() if self._frozen else 0,
            'collections_total': self._collections_total,
            'collected_total': self._collected_total,
            'last_collected': self._last_collected,
            'last_duration_ms': self._last_duration_ms,
            'max_duration_ms': self._max_duration_ms,
            'freeze_after_seconds': self.freeze_after_seconds,
            'collect_interval_seconds': self.collect_interval_seconds,
        }
