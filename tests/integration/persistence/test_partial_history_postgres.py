"""Verify partial history index migration against PostgreSQL, without shared tables."""

import importlib
import os
import uuid

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine

MIGRATION = importlib.import_module('langbot.pkg.persistence.alembic.versions.0039_execution_lease_indexes')


@pytest.mark.asyncio
@pytest.mark.parametrize('table,index,columns', MIGRATION.INDEXES)
async def test_partial_history_indexes(table, index, columns):
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Disposable TEST_POSTGRES_URL required')
    schema = 'partial_' + uuid.uuid4().hex
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})

    def exercise(connection):
        metadata = sa.MetaData()
        present = set(columns) - {columns[-1]}
        model = sa.Table(table, metadata, *(sa.Column(name, sa.String) for name in sorted(present)))
        metadata.create_all(connection)
        connection.execute(model.insert().values(**{name: 'history' for name in present}))
        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.upgrade()
            MIGRATION.upgrade()
            indexes = {item['name'] for item in sa.inspect(connection).get_indexes(table)}
            assert index not in indexes
            assert indexes == {
                name for target, name, required in MIGRATION.INDEXES if target == table and set(required) <= present
            }
            assert connection.scalar(sa.select(sa.func.count()).select_from(model)) == 1
            MIGRATION.downgrade()
            assert not sa.inspect(connection).get_indexes(table)

    try:
        async with admin.begin() as connection:
            await connection.execute(sa.text(f'CREATE SCHEMA {schema}'))
        async with engine.begin() as connection:
            await connection.run_sync(exercise)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(sa.text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        await admin.dispose()
