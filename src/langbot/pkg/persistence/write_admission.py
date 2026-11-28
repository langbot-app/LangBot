"""Experimental writer admission shared by opted-in transactions on one Core engine."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import logging
import sqlite3
from time import perf_counter
import typing

import sqlalchemy
from sqlalchemy import event
import aiosqlite

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


SQLITE_BUSY_ERROR_CODES = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})
SQLITE_RETRY_DEFAULT_BUDGET_SECONDS = 30.0
SQLITE_RETRY_ATTEMPT_TIMEOUT_SECONDS = 5.0
SQLITE_RETRY_MAX_ATTEMPTS = 8
SQLITE_RETRY_BASE_DELAY_SECONDS = 0.02
SQLITE_RETRY_MAX_DELAY_SECONDS = 0.5

_sqlite_write_deadline: ContextVar[float | None] = ContextVar('_sqlite_write_deadline', default=None)

_T = typing.TypeVar('_T')


class _WriterQueue(asyncio.Lock):
    owner: asyncio.Task | None = None

    async def acquire(self):
        if self.owner is asyncio.current_task():
            raise RuntimeError('A queued SQLite writer cannot open an independent write transaction in the same task')
        await super().acquire()
        self.owner = asyncio.current_task()
        return True

    def release(self):
        self.owner = None
        super().release()


def enable_sqlite_write_queue(engine: AsyncEngine, *, monitoring=True) -> None:
    engine.update_execution_options(langbot_sqlite_write_queue=_WriterQueue(), langbot_queue_monitoring=monitoring)


@dataclass
class _Sample:
    owner: asyncio.Task
    # An independent transaction (e.g. lease registration) can use another
    # connection in this task. Match the first DML to the connection committing.
    first: dict = field(default_factory=dict)
    summary_seconds: float = 0
    committing: object = None
    result: tuple | None = None


_sample = ContextVar('_sqlite_write_sample', default=None)
_log = logging.getLogger(__name__)


def _owned_sample():
    sample = _sample.get()
    return sample if sample is not None and sample.owner is asyncio.current_task() else None


def enable_sqlite_write_timing(engine: AsyncEngine) -> None:
    engine.update_execution_options(langbot_sqlite_write_timing=True)

    @event.listens_for(engine.sync_engine, 'before_cursor_execute')
    def before(connection, cursor, sql, params, context, many):
        sample = _owned_sample()
        if (
            sample is not None
            and connection not in sample.first
            and (context.isinsert or context.isupdate or context.isdelete)
        ):
            context._langbot_first_write_start = perf_counter()

    @event.listens_for(engine.sync_engine, 'after_cursor_execute')
    def after(connection, cursor, sql, params, context, many):
        start = getattr(context, '_langbot_first_write_start', None)
        if start is not None:
            _owned_sample().first[connection] = (start, perf_counter())

    @event.listens_for(engine.sync_engine, 'commit')
    def committing(connection):
        sample = _owned_sample()
        if sample is not None:
            sample.committing = connection


def timed_summary(method):
    @wraps(method)
    async def wrapped(*args, **kwargs):
        sample = _owned_sample()
        if sample is None:
            return await method(*args, **kwargs)
        start = perf_counter()
        try:
            return await method(*args, **kwargs)
        finally:
            sample.summary_seconds += perf_counter() - start

    return wrapped


async def commit_write(transaction):
    await transaction.commit()
    sample = _owned_sample()
    if sample is not None:
        first = sample.first.pop(sample.committing, None)
        sample.result = (*first, perf_counter()) if first is not None else None


@asynccontextmanager
async def _timed_slot(slot, operation, queued):
    requested = perf_counter()
    sample = _Sample(asyncio.current_task())
    async with slot:
        admitted = perf_counter()
        token = _sample.set(sample)
        try:
            yield
        finally:
            _sample.reset(token)
    if sample.result is not None:
        started, written, committed = sample.result
        _log.info(
            'sqlite_write_timing op=%s queue_ms=%.3f before_write_ms=%.3f through_commit_ms=%.3f first_dml_ms=%.3f summary_ms=%.3f',
            operation,
            (admitted - requested) * 1000 if queued else 0,
            (written - admitted) * 1000,
            (committed - written) * 1000,
            (written - started) * 1000,
            sample.summary_seconds * 1000,
        )


def write_slot(engine: AsyncEngine, operation: str = 'ledger'):
    options = engine.sync_engine.get_execution_options()
    queue = options.get('langbot_sqlite_write_queue')
    if operation.startswith('monitoring.') and not options.get('langbot_queue_monitoring'):
        queue = None
    slot = queue or nullcontext()
    return _timed_slot(slot, operation, queue is not None) if options.get('langbot_sqlite_write_timing') else slot


@contextmanager
def sqlite_write_deadline(deadline_monotonic: float | None, *, override: bool = False) -> typing.Iterator[None]:
    """Bound nested SQLite write retries to ``deadline_monotonic``.

    Nested scopes only tighten an existing deadline by default. Pass
    ``override=True`` for bounded terminal persistence after an execution
    deadline has already elapsed.
    """
    if deadline_monotonic is None:
        yield
        return
    existing = _sqlite_write_deadline.get()
    effective = (
        float(deadline_monotonic) if override or existing is None else min(float(existing), float(deadline_monotonic))
    )
    token = _sqlite_write_deadline.set(effective)
    try:
        yield
    finally:
        _sqlite_write_deadline.reset(token)


def sqlite_error_code(exc: BaseException) -> int | None:
    """Return the SQLite primary/extended error code behind a SQLAlchemy exception."""
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        code = getattr(current, 'sqlite_errorcode', None)
        if isinstance(code, int):
            return code
        pending.extend(arg for arg in getattr(current, 'args', ()) if isinstance(arg, BaseException))
        original = getattr(current, 'orig', None)
        if isinstance(original, BaseException):
            pending.append(original)
    return None


def is_sqlite_busy(exc: BaseException) -> bool:
    """Return True for SQLite write contention, never for unrelated OperationalErrors."""
    if not isinstance(exc, sqlalchemy.exc.OperationalError):
        return False
    code = sqlite_error_code(exc)
    if code is not None:
        return (code & 0xFF) in SQLITE_BUSY_ERROR_CODES
    message = str(exc).lower()
    return 'database is locked' in message or 'database table is locked' in message


def _deadline_exceeded_busy_error(detail: str) -> sqlalchemy.exc.OperationalError:
    return sqlalchemy.exc.OperationalError(
        detail,
        {},
        sqlite3.OperationalError('database is locked'),
    )


@asynccontextmanager
async def sqlite_attempt_timeout(
    session: AsyncSession,
    engine: AsyncEngine,
    remaining_seconds: float,
    *,
    max_attempt_seconds: float = SQLITE_RETRY_ATTEMPT_TIMEOUT_SECONDS,
) -> typing.AsyncIterator[None]:
    """Slice SQLite ``PRAGMA busy_timeout`` for one attempt without inflating it.

    Always restores the connection's original ``busy_timeout`` before the
    pooled connection is returned.
    """
    if engine.dialect.name != 'sqlite':
        yield
        return
    if remaining_seconds > 0:
        try:
            async with asyncio.timeout(remaining_seconds):
                conn = await session.connection()
        except TimeoutError as exc:
            raise _deadline_exceeded_busy_error('SQLite connection checkout deadline exceeded') from exc
    else:
        conn = await session.connection()
    raw_conn = await conn.get_raw_connection()
    driver_conn = getattr(raw_conn, 'driver_connection', None)
    if not isinstance(driver_conn, aiosqlite.Connection):
        yield
        return
    orig_ms: int | None = None
    async with driver_conn.execute('PRAGMA busy_timeout') as cursor:
        row = await cursor.fetchone()
        if row and isinstance(row[0], int):
            orig_ms = row[0]
    desired_ms = max(0, int(min(max_attempt_seconds, max(0.0, remaining_seconds)) * 1000))
    sliced = orig_ms is not None and orig_ms > desired_ms
    if sliced:
        await driver_conn.execute(f'PRAGMA busy_timeout={desired_ms}')
    try:
        yield
    finally:
        if sliced and orig_ms is not None:
            try:
                await driver_conn.execute(f'PRAGMA busy_timeout={orig_ms}')
            except Exception:
                pass


async def run_sqlite_write_with_retry(
    engine: AsyncEngine,
    operation: typing.Callable[[float], typing.Awaitable[_T]],
    *,
    slot_operation: str = 'ledger',
    budget_seconds: float = SQLITE_RETRY_DEFAULT_BUDGET_SECONDS,
    attempt_timeout_seconds: float = SQLITE_RETRY_ATTEMPT_TIMEOUT_SECONDS,
    max_attempts: int | None = None,
    base_delay_seconds: float | None = None,
    max_delay_seconds: float | None = None,
    is_retryable: typing.Callable[[BaseException], bool] | None = None,
) -> _T:
    """Run one replay-safe write transaction under a shared monotonic deadline.

    ``write_slot`` admission, per-attempt ``PRAGMA busy_timeout`` slices, and
    exponential backoff share one monotonic deadline so retries never multiply
    ``busy_timeout`` or outlast the caller's remaining budget.
    """
    loop = asyncio.get_running_loop()
    now = loop.time()
    deadline = now + max(0.0, float(budget_seconds))
    context_deadline = _sqlite_write_deadline.get()
    if context_deadline is not None:
        deadline = min(deadline, float(context_deadline))

    effective_max_attempts = max(1, int(SQLITE_RETRY_MAX_ATTEMPTS if max_attempts is None else max_attempts))
    effective_base_delay = max(
        0.0, float(SQLITE_RETRY_BASE_DELAY_SECONDS if base_delay_seconds is None else base_delay_seconds)
    )
    effective_max_delay = max(
        0.0, float(SQLITE_RETRY_MAX_DELAY_SECONDS if max_delay_seconds is None else max_delay_seconds)
    )
    attempt = 0

    while True:
        remaining = max(0.0, deadline - loop.time())
        slot = write_slot(engine, slot_operation)
        try:
            if hasattr(slot, '__aenter__'):
                queue = engine.sync_engine.get_execution_options().get('langbot_sqlite_write_queue')
                if remaining <= 0 and isinstance(queue, _WriterQueue) and queue.locked():
                    raise _deadline_exceeded_busy_error('SQLite write admission deadline exceeded')
                if remaining > 0:
                    try:
                        async with asyncio.timeout(remaining):
                            await slot.__aenter__()
                    except TimeoutError as exc:
                        raise _deadline_exceeded_busy_error('SQLite write admission deadline exceeded') from exc
                else:
                    await slot.__aenter__()
                try:
                    remaining_in_slot = max(0.0, deadline - loop.time())
                    result = await operation(min(attempt_timeout_seconds, remaining_in_slot))
                except BaseException as exc:
                    await slot.__aexit__(type(exc), exc, exc.__traceback__)
                    raise
                await slot.__aexit__(None, None, None)
                return result
            with slot:
                return await operation(min(attempt_timeout_seconds, remaining))
        except Exception as exc:
            retryable = is_sqlite_busy(exc) or (is_retryable is not None and is_retryable(exc))
            attempt += 1
            remaining_after = deadline - loop.time()
            if not retryable or attempt >= effective_max_attempts or remaining_after <= 0:
                raise
            delay = min(effective_max_delay, effective_base_delay * (2 ** (attempt - 1)))
            if delay > 0:
                await asyncio.sleep(min(delay, remaining_after))
                if deadline - loop.time() <= 0:
                    raise
