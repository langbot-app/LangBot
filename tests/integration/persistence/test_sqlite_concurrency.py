from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from langbot.pkg.core import app  # noqa: F401 - initialize manager registration before database imports
from langbot.pkg.persistence.databases.sqlite import SQLiteDatabaseManager

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_writer_commits_while_independent_reader_is_open(tmp_path):
    application = SimpleNamespace(
        instance_config=SimpleNamespace(data={'database': {'sqlite': {'path': str(tmp_path / 'concurrency.db')}}})
    )
    manager = SQLiteDatabaseManager(application)
    await manager.initialize()
    engine = manager.get_engine()
    try:
        async with engine.begin() as connection:
            await connection.execute(sa.text('CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT)'))
            await connection.execute(sa.text("INSERT INTO probe VALUES (1, 'old')"))
        async with engine.connect() as reader:
            await reader.execute(sa.text('BEGIN'))
            assert (await reader.execute(sa.text('SELECT value FROM probe'))).scalar_one() == 'old'
            async with engine.connect() as writer:
                await writer.execute(sa.text('PRAGMA busy_timeout=250'))
                await writer.execute(sa.text("UPDATE probe SET value='new' WHERE id=1"))
                await writer.commit()
            await reader.rollback()
        async with engine.connect() as connection:
            assert (await connection.execute(sa.text('SELECT value FROM probe'))).scalar_one() == 'new'
    finally:
        await engine.dispose()
