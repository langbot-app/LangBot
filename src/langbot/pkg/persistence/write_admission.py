"""Experimental writer admission shared by opted-in transactions on one Core engine."""

import asyncio
from contextlib import asynccontextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import logging
from time import perf_counter

from sqlalchemy import event

from sqlalchemy.ext.asyncio import AsyncEngine


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
