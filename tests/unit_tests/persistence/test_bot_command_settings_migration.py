"""Unit tests for 0057_bot_command_settings Alembic migration and startup YAML migration."""

import importlib
import contextlib
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
    migrate_global_command_config_for_release,
)

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0057_bot_command_settings')


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
            assert settings['processors'] == []

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

    @contextlib.asynccontextmanager
    async def tenant_uow(self, workspace):
        with self.engine.begin() as conn:

            async def execute(stmt):
                return conn.execute(stmt)

            yield SimpleNamespace(execute=execute)


def _register_all_tables():
    """Register every entity so foreign keys of bots resolve regardless of test order."""
    from langbot.pkg.entity import persistence
    from langbot.pkg.utils import importutil

    importutil.import_modules_in_pkg(persistence)


@pytest.mark.asyncio
async def test_startup_migration_from_yaml_custom_prefix():
    """Startup migration reads custom prefix from instance_config.data['command'], updates bots, removes keys from YAML and records flag."""
    engine = sa.create_engine('sqlite://')
    db_metadata = sa.MetaData()

    from langbot.pkg.entity.persistence.bot import Bot
    from langbot.pkg.entity.persistence.metadata import Metadata, WorkspaceMetadata

    _register_all_tables()
    db_metadata.create_all(engine, tables=[Bot.__table__, Metadata.__table__, WorkspaceMetadata.__table__])

    with engine.begin() as conn:
        conn.execute(
            Bot.__table__.insert().values(
                uuid='bot-custom',
                name='CustomBot',
                description='desc',
                adapter='test',
                adapter_config={},
                workspace_uuid='ws-1',
                command_settings={'enabled': True, 'prefixes': ['/'], 'builtin': {'help': {'enabled': False}}},
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
        workspace_service=SimpleNamespace(get_singleton_workspace=AsyncMock(return_value=SimpleNamespace(uuid='ws-1'))),
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
        assert settings['builtin'] == {'help': {'enabled': False}}

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

    _register_all_tables()
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
                command_settings={'enabled': True, 'prefixes': ['/custom'], 'processors': []},
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


async def _release_engine(bots):
    from sqlalchemy.ext.asyncio import create_async_engine

    from langbot.pkg.entity.persistence.bot import Bot
    from langbot.pkg.entity.persistence.metadata import Metadata, WorkspaceMetadata

    _register_all_tables()
    engine = create_async_engine('sqlite+aiosqlite://')
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: sa.MetaData().create_all(
                sync, tables=[Bot.__table__, Metadata.__table__, WorkspaceMetadata.__table__]
            )
        )
        for workspace, uuid, settings in bots:
            await conn.execute(
                Bot.__table__.insert().values(
                    uuid=uuid,
                    name=uuid,
                    description='',
                    adapter='test',
                    adapter_config={},
                    workspace_uuid=workspace,
                    command_settings=settings,
                )
            )
    return engine


async def _release_state(engine):
    from langbot.pkg.entity.persistence.bot import Bot
    from langbot.pkg.entity.persistence.metadata import Metadata, WorkspaceMetadata

    async with engine.connect() as conn:
        bots = {
            uuid: json.loads(settings) if isinstance(settings, str) else settings
            for uuid, settings in (await conn.execute(sa.select(Bot.uuid, Bot.command_settings))).all()
        }
        reports = {
            workspace: json.loads(value)
            for workspace, value in (
                await conn.execute(sa.select(WorkspaceMetadata.workspace_uuid, WorkspaceMetadata.value))
            ).all()
        }
        flag = (
            await conn.execute(sa.select(Metadata.value).where(Metadata.key == MIGRATION_FLAG_KEY))
        ).scalar_one_or_none()
    return bots, reports, flag


@pytest.mark.asyncio
async def test_release_migration_carries_legacy_prefixes_to_every_workspace():
    """Cloud skips the startup migration, so the release job applies config.yaml's prefixes to all workspaces once."""
    engine = await _release_engine(
        [
            ('ws-1', 'bot-a', {'enabled': True, 'prefixes': ['/'], 'builtin': {'help': {'enabled': False}}}),
            ('ws-1', 'bot-b', {'enabled': True, 'prefixes': ['/'], 'processors': []}),
            ('ws-2', 'bot-c', {'enabled': True, 'prefixes': ['/'], 'processors': []}),
        ]
    )
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'command': {'enable': True, 'prefix': ['!', '！'], 'privilege': {}}}),
        logger=Mock(),
    )
    try:
        await migrate_global_command_config_for_release(ap, engine)
        bots, reports, flag = await _release_state(engine)
        assert {uuid: settings['prefixes'] for uuid, settings in bots.items()} == {
            'bot-a': ['!', '！'],
            'bot-b': ['!', '！'],
            'bot-c': ['!', '！'],
        }
        assert bots['bot-a']['builtin'] == {'help': {'enabled': False}}
        assert set(reports) == {'ws-1', 'ws-2'}
        assert reports['ws-1']['original_prefixes'] == ['!', '！']
        assert flag == 'true'
        # The shared config file is left alone.
        assert ap.instance_config.data['command']['prefix'] == ['!', '！']

        # A later release (or a bot changed by its owner since) is not touched again.
        from langbot.pkg.entity.persistence.bot import Bot

        async with engine.begin() as conn:
            await conn.execute(
                Bot.__table__.update().where(Bot.uuid == 'bot-c').values(command_settings={'prefixes': ['#']})
            )
        await migrate_global_command_config_for_release(ap, engine)
        bots, reports, _ = await _release_state(engine)
        assert bots['bot-c'] == {'prefixes': ['#']}
        assert len(reports) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_release_migration_without_legacy_section_only_records_flag():
    engine = await _release_engine([('ws-1', 'bot-a', {'enabled': True, 'prefixes': ['/'], 'processors': []})])
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'command': {'privilege': {}}}), logger=Mock())
    try:
        await migrate_global_command_config_for_release(ap, engine)
        bots, reports, flag = await _release_state(engine)
        assert bots['bot-a']['prefixes'] == ['/']
        assert reports == {}
        assert flag == 'true'
    finally:
        await engine.dispose()
