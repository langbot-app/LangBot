"""Enforce the read boundary and the schema needed for bounded repair."""

import ast
import datetime
import importlib
import importlib.util
import inspect

import pytest

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence import monitoring as monitoring_models
from langbot.pkg.entity.persistence.monitoring import MonitoringSession, MonitoringSessionReceipt
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.persistence import session_summary_reader, session_summary_contract
from langbot.pkg.persistence.tenant_uow import TENANT_TABLE_COLUMNS


pytestmark = pytest.mark.session_summary


def assert_summary_dependencies(source, package):
    """Restrict historical and application capabilities, not utility/type imports."""
    forbidden = (
        'langbot.pkg.agent',
        'langbot.pkg.api',
        'langbot.pkg.core',
        'langbot.pkg.pipeline',
        'langbot.pkg.persistence.mgr',
        'langbot.pkg.persistence.session_summary_backfill',
        'langbot.pkg.persistence.session_summary_writer',
        'langbot.pkg.entity.persistence',
    )
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            target = importlib.util.resolve_name('.' * node.level + (node.module or ''), package)
            imports = [target + '.' + alias.name for alias in node.names]
            if target == monitoring_models.__name__:
                for alias in node.names:
                    model = getattr(monitoring_models, alias.name, None)
                    table = getattr(model, '__table__', None)
                    assert alias.name != '*' and (table is None or table.name == 'monitoring_sessions')
                continue
        elif isinstance(node, ast.Import):
            imports = [alias.name for alias in node.names]
        else:
            continue
        for target in imports:
            assert not any(target == prefix or target.startswith(prefix + '.') for prefix in forbidden), target
            assert target != monitoring_models.__name__, 'Import the summary model without the history namespace'


@pytest.mark.contract('reader_dependencies')
def test_list_modules_have_no_history_or_application_capabilities():
    for module in (session_summary_contract, session_summary_reader):
        assert_summary_dependencies(inspect.getsource(module), module.__package__)


@pytest.mark.parametrize(
    'extra_import', ['from typing import Any', 'import functools', 'from datetime import timezone']
)
def test_summary_dependency_check_allows_utility_and_type_imports(extra_import):
    assert_summary_dependencies(extra_import, session_summary_reader.__package__)


@pytest.mark.parametrize(
    'extra_import',
    [
        'from ..entity.persistence.monitoring import MonitoringMessage',
        'from .session_summary_backfill import SessionSummaryBackfill',
        'from ..entity.persistence import event_log',
        'from ..entity.persistence.agent_run import AgentRun',
    ],
)
def test_summary_dependency_check_rejects_history_and_repair(extra_import):
    with pytest.raises(AssertionError):
        assert_summary_dependencies(extra_import, session_summary_reader.__package__)


@pytest.mark.contract('summary_schema')
def test_summary_migration_is_idempotent_and_preserves_legacy_counts():
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0040_session_summaries')
    engine = sa.create_engine('sqlite:///:memory:')

    @sa.event.listens_for(engine, 'connect')
    def foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')

    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            connection.execute(sa.insert(Workspace).values(uuid='w', instance_uuid='i', name='W', slug='w'))
            connection.execute(
                sa.text(
                    'INSERT INTO monitoring_sessions (workspace_uuid,bot_id,session_id,bot_name,pipeline_id,pipeline_name,'
                    'message_count,start_time,last_activity,is_active,user_id,user_name,platform) '
                    "VALUES ('w','b','s','Bot','legacy','Legacy Pipeline',99,:now,:now,1,'legacy-user','Legacy User','legacy')"
                ),
                {'now': datetime.datetime(2026, 1, 1)},
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
            row = connection.execute(sa.select(MonitoringSession)).mappings().one()
            assert row['message_count'] == 99 and row['source_count'] == 0
            assert row['metadata_role'] is None and row['metadata_timestamp'] is None
            assert row['metadata_source_key'] is None and row['base_snapshot'] is None
            assert (row['user_id'], row['user_name'], row['platform']) == ('legacy-user', 'Legacy User', 'legacy')
            assert (row['pipeline_id'], row['pipeline_name']) == ('legacy', 'Legacy Pipeline')
            assert connection.execute(sa.select(WorkspaceMetadata.value)).scalar_one() == '{"source": "messages"}'
            inspector = sa.inspect(connection)
            assert inspector.get_pk_constraint('monitoring_session_receipts')['constrained_columns'] == [
                'workspace_uuid',
                'bot_id',
                'source_key',
            ]
            assert inspector.get_foreign_keys('monitoring_session_receipts')[0]['options']['ondelete'] == 'CASCADE'
            assert TENANT_TABLE_COLUMNS['monitoring_session_receipts'] == 'workspace_uuid'
            for table, index, fields in migration.INDEXES:
                indexes = {item['name']: item['column_names'] for item in inspector.get_indexes(table)}
                assert indexes[index] == fields
            connection.execute(
                sa.insert(MonitoringSessionReceipt).values(
                    workspace_uuid='w',
                    bot_id='b',
                    source_key='event:detached',
                    role='event',
                    covered=True,
                    timestamp=datetime.datetime(2026, 1, 1),
                )
            )
            connection.execute(sa.delete(Workspace).where(Workspace.uuid == 'w'))
            assert (
                connection.execute(sa.select(sa.func.count()).select_from(MonitoringSessionReceipt)).scalar_one() == 0
            )
    finally:
        engine.dispose()
