"""Reclaim free pages without rebuilding a live SQLite database."""

import asyncio
import sqlite3
import time
from weakref import WeakKeyDictionary


_states = WeakKeyDictionary()
MIN_PAGES = 1
MAX_PAGES = 512
TARGET_SECONDS = 0.025
ROUND_SECONDS = 2.0
PAUSE_SECONDS = 0.25


class _State:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.pages = 8


async def reclaim_free_pages(engine):
    """Adapt batch size to measured latency; yield immediately to other writers.

    The round budget stops new batches, but cannot bound an in-flight SQLite
    operation. Each completed statement releases its write transaction before
    sleeping. The connection's original busy timeout is restored before pooling.
    """
    if engine.dialect.name != 'sqlite':
        return
    if engine.url.database in (None, '', ':memory:') or engine.url.query.get('mode') == 'memory':
        return
    state = _states.setdefault(engine, _State())
    if state.lock.locked():
        return
    async with state.lock:
        deadline = time.monotonic() + ROUND_SECONDS
        async with engine.connect() as connection:
            connection = await connection.execution_options(isolation_level='AUTOCOMMIT')
            if (await connection.exec_driver_sql('PRAGMA auto_vacuum')).scalar_one() != 2:
                raise RuntimeError('SQLite incremental vacuum migration is required')
            timeout = (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one()
            await connection.exec_driver_sql('PRAGMA busy_timeout=0')
            driver = (await connection.get_raw_connection()).driver_connection
            try:
                while time.monotonic() < deadline:
                    if (await connection.exec_driver_sql('PRAGMA freelist_count')).scalar_one() == 0:
                        break
                    started = time.monotonic()
                    try:
                        # SQLite advances incremental vacuum while stepping the
                        # cursor despite exposing no result columns. SQLAlchemy
                        # closes such results early, so drain the driver cursor.
                        cursor = await driver.execute(f'PRAGMA incremental_vacuum({state.pages})')
                        try:
                            await cursor.fetchall()
                        finally:
                            await cursor.close()
                    except sqlite3.OperationalError as exc:
                        code = getattr(exc, 'sqlite_errorcode', None)
                        if code is None or code & 255 not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                            raise
                        state.pages = max(MIN_PAGES, state.pages // 2)
                        break
                    elapsed = time.monotonic() - started
                    if elapsed > TARGET_SECONDS:
                        state.pages = max(MIN_PAGES, state.pages // 2)
                    elif elapsed < TARGET_SECONDS / 2:
                        state.pages = min(MAX_PAGES, state.pages * 2)
                    if time.monotonic() + PAUSE_SECONDS >= deadline:
                        break
                    await asyncio.sleep(PAUSE_SECONDS)
            finally:
                await connection.exec_driver_sql(f'PRAGMA busy_timeout={timeout}')
