"""Move existing plugin routes without discarding primary routes or disabled state."""

import importlib
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0025_bot_plugin_processors')


@pytest.mark.parametrize('column_exists', [False, True])
def test_migrate_duplicate_routes_and_preserve_primary_and_disabled(column_exists):
    engine = sa.create_engine('sqlite://')
    metadata = sa.MetaData()
    columns = [sa.Column('uuid', sa.String(), primary_key=True), sa.Column('event_bindings', sa.JSON())]
    if column_exists:
        columns.append(sa.Column('plugin_processors', sa.JSON(), server_default='[]'))
    table = sa.Table('bots', metadata, *columns)
    metadata.create_all(engine)
    primary = {'target_type': 'agent', 'target_uuid': 'agent', 'event_pattern': '*'}
    with engine.begin() as conn:
        conn.execute(
            table.insert().values(
                uuid='bot',
                event_bindings=[
                    primary,
                    {'target_type': 'event_processor', 'target_uuid': 'one', 'enabled': False},
                    {'target_type': 'event_processor', 'target_uuid': 'one', 'enabled': True},
                    {'target_type': 'event_processor', 'target_uuid': 'two', 'enabled': False},
                ],
            )
        )
        with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
            migration.upgrade()
            migrated = sa.Table('bots', sa.MetaData(), autoload_with=conn)
            row = conn.execute(sa.select(migrated)).mappings().one()
            assert row['event_bindings'] == [primary]
            assert row['plugin_processors'] == [
                {'processor_uuid': 'one', 'enabled': True},
                {'processor_uuid': 'two', 'enabled': False},
            ]
            migration.upgrade()
            assert conn.execute(sa.select(migrated)).mappings().one() == row
            migration.downgrade()
            assert 'plugin_processors' not in {c['name'] for c in sa.inspect(conn).get_columns('bots')}
    engine.dispose()
