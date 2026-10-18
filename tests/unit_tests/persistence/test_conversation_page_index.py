"""Conversation paging index is safe for existing and fresh databases."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from langbot.pkg.entity.persistence.monitoring import MonitoringMessage


def test_conversation_index_migration_preserves_history_and_matches_metadata():
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0039_execution_lease_indexes')
    index_name = 'ix_monitoring_messages_conversation_page'
    engine = sa.create_engine('sqlite:///:memory:')
    metadata = sa.MetaData()
    table = sa.Table(
        'monitoring_messages',
        metadata,
        *[
            sa.Column(name, sa.String, primary_key=name == 'id')
            for name in (
                'id',
                'workspace_uuid',
                'bot_id',
                'session_id',
                'timestamp',
                'message_content',
                'status',
                'execution_lease_expires_at',
            )
        ],
    )
    sa.Index('existing_index', table.c.workspace_uuid)
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(table.insert().values(id='history', message_content='inline media'))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                indexes = {
                    index['name']: index['column_names'] for index in sa.inspect(connection).get_indexes(table.name)
                }
                expected = next(index for index in MonitoringMessage.__table__.indexes if index.name == index_name)
                assert indexes[index_name] == [column.name for column in expected.columns]
                migration.downgrade()
                assert {index['name'] for index in sa.inspect(connection).get_indexes(table.name)} == {'existing_index'}
                assert connection.scalar(sa.select(table.c.message_content)) == 'inline media'
                migration.upgrade()
    finally:
        engine.dispose()
