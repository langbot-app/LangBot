"""Tests for the dialect-neutral persistence write primitive."""

from __future__ import annotations

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.write_admission import run_write_tx


async def _create_table(engine):
    async with engine.begin() as connection:
        await connection.execute(sqlalchemy.text('CREATE TABLE values_test (value INTEGER NOT NULL)'))


async def test_run_write_tx_commits_callback(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "write-tx.db"}')
    try:
        await _create_table(engine)

        async def write(session):
            await session.execute(sqlalchemy.text('INSERT INTO values_test(value) VALUES (1)'))
            return 'written'

        assert await run_write_tx(engine, write) == 'written'
        async with engine.connect() as connection:
            assert await connection.scalar(sqlalchemy.text('SELECT COUNT(*) FROM values_test')) == 1
    finally:
        await engine.dispose()


async def test_run_write_tx_retries_explicit_domain_conflict(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "write-retry.db"}')
    attempts = 0
    try:
        await _create_table(engine)

        async def write(session):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError('sequence conflict')
            await session.execute(sqlalchemy.text('INSERT INTO values_test(value) VALUES (2)'))

        await run_write_tx(
            engine,
            write,
            retry_on=lambda exc: isinstance(exc, ValueError),
            base_delay_seconds=0,
        )
        assert attempts == 2
    finally:
        await engine.dispose()
