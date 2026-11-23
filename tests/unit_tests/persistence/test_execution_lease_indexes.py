"""Lease maintenance must not scan a Workspace's completed execution history."""

import datetime
import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine

# Register users and workspaces so create_all can resolve the foreign keys.
from langbot.pkg.entity.persistence import user, workspace  # noqa: F401
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.utils.execution_lease import reconcile_execution_leases


MIGRATION = importlib.import_module('langbot.pkg.persistence.alembic.versions.0039_execution_lease_indexes')
LEASE_INDEXES = {
    'agent_run': ('ix_agent_run_workspace_status_lease', ['workspace_id', 'status', 'execution_lease_expires_at']),
    'monitoring_messages': (
        'ix_monitoring_messages_workspace_status_lease',
        ['workspace_uuid', 'status', 'execution_lease_expires_at'],
    ),
}


def _create_schema(connection, source):
    Base.metadata.create_all(connection)
    if source == 'migration':
        for table, (index, _) in LEASE_INDEXES.items():
            next(item for item in Base.metadata.tables[table].indexes if item.name == index).drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.upgrade()


@pytest.mark.parametrize('source', ['metadata', 'migration'])
def test_lease_index_migration_preserves_data_and_existing_indexes(source):
    engine = sa.create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            _create_schema(connection, source)
            connection.execute(sa.insert(AgentRun).values(run_id='history', runner_id='runner', status='completed'))
            original_indexes = {
                table: {index['name'] for index in sa.inspect(connection).get_indexes(table)} for table in LEASE_INDEXES
            }
            with Operations.context(MigrationContext.configure(connection)):
                MIGRATION.upgrade()
                for table, (index, columns) in LEASE_INDEXES.items():
                    indexes = {item['name']: item['column_names'] for item in sa.inspect(connection).get_indexes(table)}
                    assert indexes[index] == columns
                    assert original_indexes[table] <= indexes.keys()

                MIGRATION.downgrade()
                for table in LEASE_INDEXES:
                    remaining = {item['name'] for item in sa.inspect(connection).get_indexes(table)}
                    removed = {index for index_table, index, _ in MIGRATION.INDEXES if index_table == table}
                    assert remaining == original_indexes[table] - removed
                assert connection.scalar(sa.select(AgentRun.status)) == 'completed'

                MIGRATION.upgrade()
                assert connection.scalar(sa.select(AgentRun.status)) == 'completed'
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['metadata', 'migration'])
@pytest.mark.parametrize('model', [AgentRun, MonitoringMessage])
async def test_lease_queries_use_workspace_status_expiry_index(model, source):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    now = datetime.datetime(2026, 10, 17)
    statements = []

    def capture_statement(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith(('SELECT ', 'UPDATE ')) and model.__tablename__ in statement:
            statements.append((statement, parameters))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync: _create_schema(sync, source))
            common = {
                'execution_owner_id': 'live-host',
                'execution_lease_expires_at': now - datetime.timedelta(seconds=1),
            }
            if model is AgentRun:
                rows = [
                    dict(
                        common,
                        run_id=str(i),
                        runner_id='runner',
                        workspace_id='workspace',
                        status='completed',
                        created_at=now,
                        updated_at=now,
                    )
                    for i in range(2000)
                ]
            else:
                rows = [
                    dict(
                        common,
                        id=str(i),
                        workspace_uuid='workspace',
                        timestamp=now,
                        bot_id='bot',
                        bot_name='bot',
                        pipeline_id='pipeline',
                        pipeline_name='pipeline',
                        message_content='Historical message ' * 64,
                        session_id='session',
                        status='success',
                        level='info',
                    )
                    for i in range(2000)
                ]
            await connection.execute(sa.insert(model), rows)

        sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture_statement)
        try:
            assert await reconcile_execution_leases(engine, 'workspace', now=now, owner_id='live-host') == 0
        finally:
            sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture_statement)

        assert len(statements) == 2
        async with engine.connect() as connection:
            for statement, parameters in statements:
                plan = (await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + statement, parameters)).all()
                details = ' '.join(row[3] for row in plan)
                assert LEASE_INDEXES[model.__tablename__][0] in details, details
                assert 'execution_lease_expires_at' in details, details
                assert 'USE TEMP B-TREE' not in details, details
    finally:
        await engine.dispose()
