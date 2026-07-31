from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import contextvars
import threading
from collections.abc import Callable
from typing import Any


DEFAULT_MAX_WORKERS = 8
DEFAULT_MAX_PENDING = 128
DEFAULT_MAX_INFLIGHT_PER_SCOPE = 4
HARD_MAX_WORKERS = 64
HARD_MAX_PENDING = 4096
BLOCKING_CLEANUP_SCOPE = 'system:cleanup'
_CLEANUP_RETRY_INITIAL_SECONDS = 0.01
_CLEANUP_RETRY_MAX_SECONDS = 0.25

_blocking_work_scope: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'langbot_blocking_work_scope',
    default=None,
)


class BlockingWorkCapacityError(RuntimeError):
    """Raised before unbounded blocking work can enter the executor queue."""

    def __init__(self, message: str, *, scope: str | None = None) -> None:
        super().__init__(message)
        self.scope = scope


@contextlib.contextmanager
def blocking_work_scope(scope: str | None):
    """Attribute blocking submissions to one trusted tenant scope."""

    normalized = str(scope).strip() if scope is not None else None
    if not normalized:
        yield
        return
    token = _blocking_work_scope.set(normalized)
    try:
        yield
    finally:
        _blocking_work_scope.reset(token)


def current_blocking_work_scope() -> str | None:
    """Return the active trusted blocking-work scope, if any."""

    return _blocking_work_scope.get()


async def run_blocking_atomic(
    fn: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Let an admitted filesystem operation finish before propagating cancel."""

    task = asyncio.create_task(asyncio.to_thread(fn, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise


async def run_blocking_cleanup(
    fn: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Wait for bounded executor capacity and complete cleanup atomically."""

    retry_delay = _CLEANUP_RETRY_INITIAL_SECONDS
    while True:
        try:
            with blocking_work_scope(BLOCKING_CLEANUP_SCOPE):
                return await run_blocking_atomic(fn, *args, **kwargs)
        except BlockingWorkCapacityError as exc:
            if exc.scope != BLOCKING_CLEANUP_SCOPE:
                raise
            await asyncio.sleep(retry_delay)
            retry_delay = min(
                retry_delay * 2,
                _CLEANUP_RETRY_MAX_SECONDS,
            )


async def run_in_blocking_work_scope(
    coro,
    scope: str | None,
):
    """Run a coroutine with blocking-work fairness attribution."""

    with blocking_work_scope(scope):
        return await coro


def _bounded_integer(
    value: Any,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f'{name} must be an integer')
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be an integer') from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return parsed


def _validated_limits(
    max_workers: Any,
    max_pending: Any,
    max_inflight_per_scope: Any | None,
) -> tuple[int, int, int]:
    workers = _bounded_integer(
        max_workers,
        name='blocking_executor.max_workers',
        minimum=1,
        maximum=HARD_MAX_WORKERS,
    )
    pending = _bounded_integer(
        max_pending,
        name='blocking_executor.max_pending',
        minimum=0,
        maximum=HARD_MAX_PENDING,
    )
    fair_share = max(1, workers // 2)
    scope_limit = (
        min(DEFAULT_MAX_INFLIGHT_PER_SCOPE, fair_share)
        if max_inflight_per_scope is None
        else _bounded_integer(
            max_inflight_per_scope,
            name='blocking_executor.max_inflight_per_scope',
            minimum=1,
            maximum=HARD_MAX_PENDING,
        )
    )
    if scope_limit > fair_share:
        raise ValueError(f'blocking_executor.max_inflight_per_scope must not exceed half of max_workers ({fair_share})')
    return workers, pending, scope_limit


class BoundedThreadPoolExecutor(concurrent.futures.ThreadPoolExecutor):
    """Thread pool with a hard cap on running plus queued submissions."""

    def __init__(
        self,
        *,
        max_workers: int = DEFAULT_MAX_WORKERS,
        max_pending: int = DEFAULT_MAX_PENDING,
        max_inflight_per_scope: int | None = None,
        thread_name_prefix: str = 'langbot-blocking',
    ) -> None:
        max_workers, max_pending, max_inflight_per_scope = _validated_limits(
            max_workers,
            max_pending,
            max_inflight_per_scope,
        )
        super().__init__(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self.max_workers = max_workers
        self.max_pending = max_pending
        self.max_inflight_per_scope = max_inflight_per_scope
        self._capacity = threading.BoundedSemaphore(max_workers + max_pending)
        self._stats_lock = threading.Lock()
        self._inflight_by_scope: dict[str, int] = {}
        self._inflight = 0
        self._running = 0
        self._submitted_total = 0
        self._completed_total = 0
        self._rejected_total = 0
        self._global_rejected_total = 0
        self._scope_rejected_total = 0

    def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> concurrent.futures.Future:
        scope = current_blocking_work_scope()
        if not self._capacity.acquire(blocking=False):
            with self._stats_lock:
                self._rejected_total += 1
                self._global_rejected_total += 1
            raise BlockingWorkCapacityError(
                'Blocking executor capacity reached',
                scope=scope,
            )

        with self._stats_lock:
            if scope is not None and self._inflight_by_scope.get(scope, 0) >= self.max_inflight_per_scope:
                self._rejected_total += 1
                self._scope_rejected_total += 1
                self._capacity.release()
                raise BlockingWorkCapacityError(
                    'Workspace blocking executor capacity reached',
                    scope=scope,
                )
            self._inflight += 1
            self._submitted_total += 1
            if scope is not None:
                self._inflight_by_scope[scope] = self._inflight_by_scope.get(scope, 0) + 1

        def run() -> Any:
            with self._stats_lock:
                self._running += 1
            try:
                return fn(*args, **kwargs)
            finally:
                with self._stats_lock:
                    self._running -= 1

        try:
            future = super().submit(run)
        except BaseException:
            with self._stats_lock:
                self._inflight -= 1
                self._release_scope_locked(scope)
            self._capacity.release()
            raise

        def complete(_future: concurrent.futures.Future) -> None:
            with self._stats_lock:
                self._inflight -= 1
                self._completed_total += 1
                self._release_scope_locked(scope)
            self._capacity.release()

        future.add_done_callback(complete)
        return future

    def _release_scope_locked(self, scope: str | None) -> None:
        if scope is None:
            return
        remaining = self._inflight_by_scope.get(scope, 0) - 1
        if remaining > 0:
            self._inflight_by_scope[scope] = remaining
        else:
            self._inflight_by_scope.pop(scope, None)

    def snapshot(self) -> dict[str, int]:
        with self._stats_lock:
            inflight = self._inflight
            running = self._running
            return {
                'max_workers': self.max_workers,
                'max_pending': self.max_pending,
                'max_inflight_per_scope': self.max_inflight_per_scope,
                'inflight': inflight,
                'running': running,
                'pending': max(inflight - running, 0),
                'active_scopes': len(self._inflight_by_scope),
                'submitted_total': self._submitted_total,
                'completed_total': self._completed_total,
                'rejected_total': self._rejected_total,
                'global_rejected_total': self._global_rejected_total,
                'scope_rejected_total': self._scope_rejected_total,
            }


def configure_bounded_default_executor(
    loop: asyncio.AbstractEventLoop,
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    max_pending: int = DEFAULT_MAX_PENDING,
    max_inflight_per_scope: int | None = None,
    thread_name_prefix: str = 'langbot-blocking',
) -> BoundedThreadPoolExecutor:
    """Install one bounded owner for every ``asyncio.to_thread`` call."""

    max_workers, max_pending, max_inflight_per_scope = _validated_limits(
        max_workers,
        max_pending,
        max_inflight_per_scope,
    )
    existing = getattr(loop, '_default_executor', None)
    if isinstance(existing, BoundedThreadPoolExecutor):
        if (
            existing.max_workers != max_workers
            or existing.max_pending != max_pending
            or existing.max_inflight_per_scope != max_inflight_per_scope
        ):
            raise RuntimeError('The blocking executor is already configured with different limits')
        return existing
    if existing is not None:
        raise RuntimeError('The event loop default executor was initialized before LangBot resource limits')

    executor = BoundedThreadPoolExecutor(
        max_workers=max_workers,
        max_pending=max_pending,
        max_inflight_per_scope=max_inflight_per_scope,
        thread_name_prefix=thread_name_prefix,
    )
    loop.set_default_executor(executor)
    return executor
