"""Serialize SQLite writers on one application engine, without locking readers."""

from __future__ import annotations

import asyncio
import re
import time

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite.aiosqlite import AsyncAdapt_aiosqlite_connection
from sqlalchemy.util.concurrency import await_only


_TOKENS = re.compile(
    r"\ufeff|--[^\n]*(?:\n|$)|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`|\[[^\]]*\]|[A-Za-z_\x80-\U0010ffff][A-Za-z_0-9$\x80-\U0010ffff]*|[(),.=]",
    re.S,
)
_WRITES = {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP', 'VACUUM', 'REINDEX', 'ATTACH', 'DETACH'}


def _writes(statement: str) -> bool:
    words = [
        m.group()
        for m in _TOKENS.finditer(statement)
        if m.group() != '\ufeff' and not m.group().startswith(('--', '/*'))
    ]
    if not words:
        return False
    first = words[0].upper()
    if first in _WRITES:
        return True
    if first == 'BEGIN':
        return any(word.upper() in {'IMMEDIATE', 'EXCLUSIVE'} for word in words[1:])
    if first == 'PRAGMA':
        # SQLite accepts both name=value and name(value) for writable PRAGMAs.
        read_arguments = {
            'table_info',
            'table_xinfo',
            'table_list',
            'index_info',
            'index_xinfo',
            'index_list',
            'foreign_key_list',
            'foreign_key_check',
            'integrity_check',
            'quick_check',
        }
        # Only the pragma name is an identifier; arguments/comments may contain
        # '=', keywords or parentheses without changing a read into a write.
        name_index = 3 if len(words) > 3 and words[2] == '.' else 1
        if len(words) <= name_index:
            return False
        name = words[name_index].strip('"\'`[]').lower()
        argument = words[name_index + 1 : name_index + 2]
        return name in {'incremental_vacuum', 'wal_checkpoint', 'optimize'} or (
            argument in (['='], ['(']) and name not in read_arguments
        )
    if first == 'WITH':
        index = 2 if len(words) > 1 and words[1].upper() == 'RECURSIVE' else 1

        def group_end(start):
            depth = 0
            for position in range(start, len(words)):
                if words[position] == '(':
                    depth += 1
                elif words[position] == ')':
                    depth -= 1
                    if depth == 0:
                        return position + 1
            return len(words)

        while index < len(words):
            index += 1  # CTE name, including identifiers that resemble keywords.
            if index < len(words) and words[index] == '(':
                index = group_end(index)  # Optional column names.
            if index >= len(words) or words[index].upper() != 'AS':
                return False
            index += 1
            while index < len(words) and words[index].upper() in {'NOT', 'MATERIALIZED'}:
                index += 1
            if index >= len(words) or words[index] != '(':
                return False
            index = group_end(index)
            if index < len(words) and words[index] == ',':
                index += 1
                continue
            return index < len(words) and words[index].upper() in _WRITES
    return False


class SQLiteWriteGate:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.loop = None
        self.failed = False
        self.waiting = 0
        self.acquisitions = 0
        self.wait_seconds = 0.0
        self.max_wait_seconds = 0.0

    def check(self):
        loop = asyncio.get_running_loop()
        if self.loop is None:
            self.loop = loop
        elif self.loop is not loop:
            raise RuntimeError('SQLite writer gate belongs to another event loop; create a new engine for this loop')
        if self.failed:
            raise RuntimeError(
                'SQLite writer gate unavailable after connection close failure; restart the process before writing'
            )

    async def acquire(self):
        self.check()
        start = time.monotonic()
        self.waiting += 1
        try:
            await self.lock.acquire()
        finally:
            self.waiting -= 1
        try:
            self.check()
        except BaseException:
            self.lock.release()
            raise
        elapsed = time.monotonic() - start
        self.acquisitions += 1
        self.wait_seconds += elapsed
        self.max_wait_seconds = max(self.max_wait_seconds, elapsed)

    def resource_stats(self):
        return {
            'sqlite_writer_active': int(self.lock.locked()),
            'sqlite_writer_waiting': self.waiting,
            'sqlite_writer_acquisitions': self.acquisitions,
            'sqlite_writer_wait_ms_total': int(self.wait_seconds * 1000),
            'sqlite_writer_wait_ms_max': int(self.max_wait_seconds * 1000),
        }


class _GatedConnection(AsyncAdapt_aiosqlite_connection):
    """Release after DBAPI completion, not SQLAlchemy's pre-commit event."""

    __slots__ = ('gate', 'writer')

    def __init__(self, dbapi, connection, gate):
        super().__init__(dbapi, connection)
        self.gate = gate
        self.writer = False

    def release(self):
        if self.writer:
            self.writer = False
            self.gate.lock.release()

    def acquire(self):
        self.gate.check()
        if not self.writer:
            await_only(self.gate.acquire())
            self.writer = True

    def fail_closed(self):
        # Wake queued callers to fail explicitly, never admit a new writer when
        # physical close completion is uncertain. Recovery requires process restart.
        self.gate.failed = True
        self.release()

    def _terminate_force_close(self):
        try:
            stop = getattr(self.driver_connection, 'stop', None)
            closed = (
                stop() if stop is not None else asyncio.get_running_loop().create_task(self._terminate_graceful_close())
            )
            if closed is None:
                self.fail_closed()
            else:
                closed.add_done_callback(self._closed)
        except BaseException:
            self.fail_closed()
            raise

    def _closed(self, future):
        if future.cancelled() or future.exception() is not None:
            self.fail_closed()
        else:
            self.release()

    def commit(self):
        super().commit()
        self.release()

    def rollback(self):
        super().rollback()
        self.release()

    def close(self):
        try:
            super().close()
        except BaseException:
            self.fail_closed()
            raise
        self.release()

    async def _terminate_graceful_close(self):
        try:
            await self.driver_connection.close()
        except BaseException:
            self.fail_closed()
            raise
        self.release()


def install(engine):
    """Cover ORM flushes, Core statements and direct SQL on this async engine."""
    if engine.dialect.name != 'sqlite':
        return None
    # shortcut: one runtime engine/process; independent writers need PostgreSQL.
    gate = SQLiteWriteGate()

    def connect(dialect, connection_record, args, kwargs):
        gate.check()
        adapted = dialect.loaded_dbapi.connect(*args, **kwargs)
        return _GatedConnection(dialect.loaded_dbapi, adapted.driver_connection, gate)

    def before(connection, cursor, statement, parameters, context, executemany):
        gate.check()
        if context.compiled is not None and context.compiled.statement.is_select:
            return
        if context.isinsert or context.isupdate or context.isdelete or _writes(statement):
            connection.connection.dbapi_connection.acquire()

    def after(connection, cursor, statement, parameters, context, executemany):
        adapted = connection.connection.dbapi_connection
        # Autocommit DDL/DML and releasing the outermost SAVEPOINT end the
        # physical transaction even if SQLAlchemy still has an autobegin object.
        if not adapted.driver_connection.in_transaction:
            adapted.release()

    def reset(connection, record, state):
        # A failed SQLite COMMIT can retain its transaction after SQLAlchemy
        # marks it inactive. Pool reset must not skip that physical rollback.
        if connection.writer:
            if state.asyncio_safe:
                connection.rollback()
            elif not engine.dialect.has_terminate:
                # Older SQLAlchemy/aiosqlite cannot terminate from GC themselves.
                connection._terminate_force_close()

    sa.event.listen(engine.sync_engine, 'reset', reset)
    sa.event.listen(engine.sync_engine, 'do_connect', connect)
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', before)
    sa.event.listen(engine.sync_engine, 'after_cursor_execute', after)
    return gate
