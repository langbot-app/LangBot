"""Unit tests for 0043_bot_command_settings migration."""

import importlib
import json
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0043_bot_command_settings')


def test_migration_upgrade_and_downgrade():
    engine = sa.create_engine('sqlite://')
    db_metadata = sa.MetaData()

    bots_table = sa.Table(
        'bots',
        db_metadata,
        sa.Column('uuid', sa.String(), primary_key=True),
    )
    metadata_table = sa.Table(
        'metadata',
        db_metadata,
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
    )
    db_metadata.create_all(engine)

    old_config = {
        'command': {
            'enable': False,
            'prefix': ['!', '//'],
        }
    }

    with engine.begin() as conn:
        conn.execute(bots_table.insert().values(uuid='bot-1'))
        conn.execute(bots_table.insert().values(uuid='bot-2'))
        conn.execute(
            metadata_table.insert().values(
                key='instance_config',
                value=json.dumps(old_config),
            )
        )

        with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
            migration.upgrade()

            migrated_bots = sa.Table('bots', sa.MetaData(), autoload_with=conn)
            cols = {c['name'] for c in sa.inspect(conn).get_columns('bots')}
            assert 'command_settings' in cols

            rows = conn.execute(sa.select(migrated_bots)).mappings().all()
            for r in rows:
                settings = r['command_settings']
                if isinstance(settings, str):
                    settings = json.loads(settings)
                assert settings['enabled'] is False
                assert settings['prefixes'] == ['!', '//']
                assert settings['plugins'] == []

            cfg_row = conn.execute(
                sa.select(metadata_table.c.value).where(metadata_table.c.key == 'instance_config')
            ).scalar_one()
            cfg_data = json.loads(cfg_row)
            assert 'enable' not in cfg_data.get('command', {})
            assert 'prefix' not in cfg_data.get('command', {})

            # Downgrade
            migration.downgrade()
            cols_after = {c['name'] for c in sa.inspect(conn).get_columns('bots')}
            assert 'command_settings' not in cols_after

            cfg_restored = conn.execute(
                sa.select(metadata_table.c.value).where(metadata_table.c.key == 'instance_config')
            ).scalar_one()
            cfg_restored_data = json.loads(cfg_restored)
            assert cfg_restored_data['command']['enable'] is False
            assert cfg_restored_data['command']['prefix'] == ['!', '//']


def test_migration_default_when_no_global_config():
    engine = sa.create_engine('sqlite://')
    db_metadata = sa.MetaData()

    bots_table = sa.Table(
        'bots',
        db_metadata,
        sa.Column('uuid', sa.String(), primary_key=True),
    )
    metadata_table = sa.Table(
        'metadata',
        db_metadata,
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
    )
    db_metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(bots_table.insert().values(uuid='bot-default'))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
            migration.upgrade()

            migrated_bots = sa.Table('bots', sa.MetaData(), autoload_with=conn)
            row = conn.execute(sa.select(migrated_bots)).mappings().one()
            settings = row['command_settings']
            if isinstance(settings, str):
                settings = json.loads(settings)
            assert settings['enabled'] is True
            assert settings['prefixes'] == ['/']
            assert settings['plugins'] == []
