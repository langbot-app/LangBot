"""Experimental writer admission shared by opted-in transactions on one Core engine."""

import asyncio
from contextlib import nullcontext

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


def enable_sqlite_write_queue(engine: AsyncEngine) -> None:
    engine.update_execution_options(langbot_sqlite_write_queue=_WriterQueue())


def write_slot(engine: AsyncEngine):
    return engine.sync_engine.get_execution_options().get('langbot_sqlite_write_queue') or nullcontext()
