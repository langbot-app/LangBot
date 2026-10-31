import os

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.alembic_runner import run_alembic_upgrade, run_alembic_downgrade, run_alembic_stamp


@pytest.mark.asyncio
@pytest.mark.parametrize('database', ['sqlite', 'postgres'])
async def test_workflow_upgrade_and_downgrade(tmp_path, database):
    url = f'sqlite+aiosqlite:///{tmp_path / "workflow.db"}'
    if database == 'postgres':
        url = os.environ.get('TEST_POSTGRES_URL')
        if not url:
            pytest.skip('TEST_POSTGRES_URL not set')
    engine = create_async_engine(url)
    tables = {'workflows', 'workflow_versions', 'workflow_executions', 'workflow_node_executions'}
    try:
        if database == 'postgres':
            async with engine.begin() as connection:
                await connection.execute(
                    sa.text('CREATE TABLE IF NOT EXISTS workspaces (uuid VARCHAR(36) PRIMARY KEY)')
                )
            await run_alembic_stamp(engine, '0042_sqlite_incremental_vacuum')
        else:
            await run_alembic_upgrade(engine, '0042_sqlite_incremental_vacuum')
        await run_alembic_upgrade(engine, '0043_workflow_tables')
        async with engine.connect() as connection:
            actual = await connection.run_sync(lambda conn: set(sa.inspect(conn).get_table_names()))
            assert tables <= actual
            for table in tables:
                columns = await connection.run_sync(lambda conn: sa.inspect(conn).get_columns(table))
                workspace_column = next(column for column in columns if column['name'] == 'workspace_uuid')
                assert not workspace_column['nullable']
            if database == 'postgres':
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
