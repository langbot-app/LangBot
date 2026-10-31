"""Unit tests for 0043_bot_command_settings Alembic migration and startup YAML migration."""

import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from langbot.pkg.persistence.bot_command_migration import (
    MIGRATION_FLAG_KEY,
    migrate_global_command_config,
)

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0043_bot_command_settings')


def test_alembic_0043_upgrade_and_downgrade():
    """Alembic migration adds command_settings column with defaults and drops it on downgrade."""
    engine = sa.create_engine('sqlite://')
    db_metadata = sa.MetaData()

    bots_table = sa.Table(
        'bots',
        db_metadata,
        sa.Column('uuid', sa.String(), primary_key=True),
        sa.Column('workspace_uuid', sa.String(), nullable=False),
    )
    db_metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(bots_table.insert().values(uuid='bot-1', workspace_uuid='ws-1'))

        with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
            migration.upgrade()

            migrated_bots = sa.Table('bots', sa.MetaData(), autoload_with=conn)
            cols = {c['name'] for c in sa.inspect(conn).get_columns('bots')}
            assert 'command_settings' in cols

            row = conn.execute(sa.select(migrated_bots)).mappings().one()
            settings = row['command_settings']
            if isinstance(settings, str):
                settings = json.loads(settings)
            assert settings['enabled'] is True
            assert settings['prefixes'] == ['/']
            assert settings['plugins'] == []

            # Downgrade drops column
            migration.downgrade()
            cols_after = {c['name'] for c in sa.inspect(conn).get_columns('bots')}
            assert 'command_settings' not in cols_after


class FakePersistenceMgr:
    def __init__(self, engine):
        self.engine = engine
        self.mode = None

    async def execute_async(self, stmt, *args, **kwargs):
        with self.engine.begin() as conn:
            return conn.execute(stmt, *args, **kwargs)


@pytest.mark.asyncio
async def test_startup_migration_from_yaml_custom_prefix():
    """Startup migration reads custom prefix from instance_config.data['command'], updates bots, removes keys from YAML and records flag."""
    engine = sa.create_engine('sqlite://')
    db_metadata = sa.MetaData()

    from langbot.pkg.entity.persistence.bot import Bot
    from langbot.pkg.entity.persistence.metadata import Metadata

    db_metadata.create_all(engine, tables=[Bot.__table__, Metadata.__table__])

    with engine.begin() as conn:
        conn.execute(
            Bot.__table__.insert().values(
                uuid='bot-custom',
                name='CustomBot',
                description='desc',
                adapter='test',
                adapter_config={},
                workspace_uuid='ws-1',
                command_settings={'enabled': True, 'prefixes': ['/'], 'plugins': []},
            )
        )

    dump_mock = AsyncMock()
    instance_config = SimpleNamespace(
        data={
            'command': {
                'enable': True,
                'prefix': ['!', '！'],
            }
        },
        dump_config=dump_mock,
    )
    ap = SimpleNamespace(
        persistence_mgr=FakePersistenceMgr(engine),
        instance_config=instance_config,
        logger=Mock(),
    )

    await migrate_global_command_config(ap)

    # 1. Bots were updated to custom prefixes
    with engine.begin() as conn:
        row = conn.execute(sa.select(Bot.__table__).where(Bot.__table__.c.uuid == 'bot-custom')).mappings().one()
        settings = row['command_settings']
        if isinstance(settings, str):
            settings = json.loads(settings)
        assert settings['prefixes'] == ['!', '！']
        assert settings['enabled'] is True

        # 2. Flag recorded in metadata table
        flag = conn.execute(
            sa.select(Metadata.__table__.c.value).where(Metadata.__table__.c.key == MIGRATION_FLAG_KEY)
        ).scalar_one_or_none()
        assert flag == 'true'

    # 3. Keys removed from YAML and dump_config called
    assert 'enable' not in instance_config.data['command']
    assert 'prefix' not in instance_config.data['command']
    dump_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_migration_does_not_run_second_time_on_restart():
    """Startup migration skips execution if flag already exists in metadata."""
    engine = sa.create_engine('sqlite://')
    db_metadata = sa.MetaData()

    from langbot.pkg.entity.persistence.bot import Bot
    from langbot.pkg.entity.persistence.metadata import Metadata

    db_metadata.create_all(engine, tables=[Bot.__table__, Metadata.__table__])

    with engine.begin() as conn:
        conn.execute(
            Bot.__table__.insert().values(
                uuid='bot-existing',
                name='ExistingBot',
                description='desc',
                adapter='test',
                adapter_config={},
                workspace_uuid='ws-1',
                command_settings={'enabled': True, 'prefixes': ['/custom'], 'plugins': []},
            )
        )
        conn.execute(
            Metadata.__table__.insert().values(
                key=MIGRATION_FLAG_KEY,
                value='true',
            )
        )

    dump_mock = AsyncMock()
    instance_config = SimpleNamespace(
        data={
            'command': {
                'enable': True,
                'prefix': ['#'],
            }
        },
        dump_config=dump_mock,
    )
    ap = SimpleNamespace(
        persistence_mgr=FakePersistenceMgr(engine),
        instance_config=instance_config,
        logger=Mock(),
    )

    await migrate_global_command_config(ap)

    # dump_config was NOT called
    dump_mock.assert_not_called()

    # Bot was NOT modified
    with engine.begin() as conn:
        row = conn.execute(sa.select(Bot.__table__).where(Bot.__table__.c.uuid == 'bot-existing')).mappings().one()
        settings = row['command_settings']
        if isinstance(settings, str):
            settings = json.loads(settings)
        assert settings['prefixes'] == ['/custom']
