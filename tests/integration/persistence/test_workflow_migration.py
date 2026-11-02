import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.alembic_runner import run_alembic_upgrade, run_alembic_downgrade, run_alembic_stamp


@pytest.fixture(params=['sqlite', 'postgres'])
async def workflow_engine(tmp_path, request):
    url = f'sqlite+aiosqlite:///{tmp_path / "workflow.db"}'
    admin_engine = None
    options = {}
    if request.param == 'postgres':
        url = os.environ.get('TEST_POSTGRES_URL')
        if not url:
            pytest.skip('TEST_POSTGRES_URL not set')
        admin_engine = create_async_engine(url)
        schema = f'workflow_test_{uuid.uuid4().hex}'
        async with admin_engine.begin() as connection:
            await connection.execute(sa.text(f'CREATE SCHEMA {schema}'))
        options = {'connect_args': {'server_settings': {'search_path': schema}}}
    engine = create_async_engine(url, **options)
    try:
        yield engine
    finally:
        await engine.dispose()
        if admin_engine is not None:
            async with admin_engine.begin() as connection:
                await connection.execute(sa.text(f'DROP SCHEMA {schema} CASCADE'))
            await admin_engine.dispose()


@pytest.mark.asyncio
async def test_workflow_upgrade_without_workspace_table(workflow_engine):
    await run_alembic_stamp(workflow_engine, '0042_sqlite_incremental_vacuum')
    await run_alembic_upgrade(workflow_engine, '0043_workflow_tables')
    async with workflow_engine.connect() as connection:
        tables = await connection.run_sync(lambda conn: set(sa.inspect(conn).get_table_names()))
        assert tables == {'alembic_version'}
    await run_alembic_downgrade(workflow_engine, '0042_sqlite_incremental_vacuum')


@pytest.mark.asyncio
async def test_workflow_upgrade_and_downgrade(workflow_engine):
    engine = workflow_engine
    tables = {'workflows', 'workflow_versions', 'workflow_executions', 'workflow_node_executions'}
    try:
        async with engine.begin() as connection:
            await connection.execute(sa.text('CREATE TABLE workspaces (uuid VARCHAR(36) PRIMARY KEY)'))
        await run_alembic_stamp(engine, '0042_sqlite_incremental_vacuum')
        await run_alembic_upgrade(engine, '0043_workflow_tables')
        async with engine.connect() as connection:
            actual = await connection.run_sync(lambda conn: set(sa.inspect(conn).get_table_names()))
            assert tables <= actual
            for table in tables:
                columns = await connection.run_sync(lambda conn: sa.inspect(conn).get_columns(table))
                workspace_column = next(column for column in columns if column['name'] == 'workspace_uuid')
                assert not workspace_column['nullable']
            if engine.dialect.name == 'postgresql':
                policies = await connection.execute(
                    sa.text("SELECT tablename FROM pg_policies WHERE policyname = 'langbot_workspace_isolation'")
                )
                assert tables <= set(policies.scalars())
        await run_alembic_downgrade(engine, '0042_sqlite_incremental_vacuum')
        async with engine.connect() as connection:
            actual = await connection.run_sync(lambda conn: set(sa.inspect(conn).get_table_names()))
            assert tables.isdisjoint(actual)
    finally:
        await engine.dispose()
