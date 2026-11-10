"""0049: trigger, safety and general output settings move from Messaging to bots.

Runs on SQLite always and on PostgreSQL when ``TEST_POSTGRES_URL`` is set
(each test works in its own throwaway schema).
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.message_policy import schema as policy_schema

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0049_bot_message_policy')


def legacy_config(prefix: str, *, limitation: int = 60, at_sender: bool = True) -> dict:
    """A full pre-policy Messaging config, distinguishable by its settings."""
    return {
        'trigger': {
            'group-respond-rules': {'at': True, 'prefix': [prefix], 'regexp': [], 'random': 0.0},
            'access-control': {'mode': 'blacklist', 'blacklist': [f'person_{prefix}'], 'whitelist': []},
            'ignore-rules': {'prefix': [], 'regexp': []},
            'message-aggregation': {'enabled': False, 'delay': 1.5},
            'misc': {'combine-quote-message': True},
        },
        'safety': {
            'content-filter': {'scope': 'all', 'check-sensitive-words': True},
            'rate-limit': {'window-length': 60, 'limitation': limitation, 'strategy': 'drop'},
        },
        'ai': {'runner': {'id': f'plugin:test/{prefix}/default', 'expire-time': 0}, 'runner_config': {}},
        'speech': {'speech-recognition': {'enable': False}},
        'output': {
            'long-text-processing': {'threshold': 1000, 'strategy': 'forward', 'font-path': ''},
            'force-delay': {'min': 0, 'max': 0},
            'misc': {
                'exception-handling': 'show-hint',
                'failure-hint': f'{prefix} failed',
                'at-sender': at_sender,
                'quote-origin': True,
                'track-function-calls': False,
                'remove-think': True,
            },
        },
    }


def route(route_id: str, target_type: str, target_uuid: str = '') -> dict:
    return {
        'id': route_id,
        'event_pattern': 'message.received',
        'target_type': target_type,
        'target_uuid': target_uuid,
        'filters': [],
        'priority': 0,
        'enabled': True,
        'order': 0,
    }


CONFIG_A = legacy_config('alpha', limitation=5)
CONFIG_B = legacy_config('beta', limitation=99, at_sender=False)
CONVERTED = {'ai': {'runner': {'id': 'plugin:test/new/default'}}, 'output': {'misc': {'remove-think': False}}}


def _tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table]:
    bots = sa.Table(
        'bots',
        metadata,
        sa.Column('uuid', sa.String(255), primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
        sa.Column('event_bindings', sa.JSON(), nullable=False),
    )
    pipelines = sa.Table(
        'legacy_pipelines',
        metadata,
        sa.Column('uuid', sa.String(255), primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
    )
    return bots, pipelines


def _seed(conn) -> None:
    metadata = sa.MetaData()
    bots, pipelines = _tables(metadata)
    metadata.create_all(conn)
    conn.execute(
        pipelines.insert(),
        [
            {'uuid': 'p-a', 'workspace_uuid': 'ws-1', 'config': copy.deepcopy(CONFIG_A)},
            {'uuid': 'p-b', 'workspace_uuid': 'ws-1', 'config': copy.deepcopy(CONFIG_B)},
            {'uuid': 'p-converted', 'workspace_uuid': 'ws-1', 'config': copy.deepcopy(CONVERTED)},
            # Same uuid as nothing else, in another workspace: must not leak across.
            {'uuid': 'p-other', 'workspace_uuid': 'ws-2', 'config': legacy_config('gamma')},
        ],
    )
    conn.execute(
        bots.insert(),
        [
            {
                # One bot, several routes with different settings, plus non-Messaging routes.
                'uuid': 'bot-multi',
                'workspace_uuid': 'ws-1',
                'event_bindings': [
                    route('r-a', 'pipeline', 'p-a'),
                    route('r-b', 'pipeline', 'p-b'),
                    route('r-agent', 'agent', 'agent-1'),
                    route('r-discard', 'discard'),
                    route('r-converted', 'pipeline', 'p-converted'),
                    route('r-missing', 'pipeline', 'p-deleted'),
                ],
            },
            # A second bot sharing processor p-a.
            {'uuid': 'bot-shared', 'workspace_uuid': 'ws-1', 'event_bindings': [route('r-shared', 'pipeline', 'p-a')]},
            {'uuid': 'bot-empty', 'workspace_uuid': 'ws-1', 'event_bindings': []},
            # Another workspace routing to a uuid that only exists in ws-1.
            {
                'uuid': 'bot-foreign',
                'workspace_uuid': 'ws-2',
                'event_bindings': [route('r-foreign', 'pipeline', 'p-a'), route('r-own', 'pipeline', 'p-other')],
            },
        ],
    )


def _value(value):
    return json.loads(value) if isinstance(value, str) else value


def _rows(conn, table_name: str) -> dict[str, dict]:
    table = sa.Table(table_name, sa.MetaData(), autoload_with=conn)
    return {row['uuid']: dict(row) for row in conn.execute(sa.select(table)).mappings()}


def _routes(conn, bot_uuid: str) -> dict[str, dict]:
    return {item['id']: item for item in _value(_rows(conn, 'bots')[bot_uuid]['event_bindings'])}


def _columns(conn, table_name: str) -> set[str]:
    return {column['name'] for column in sa.inspect(conn).get_columns(table_name)}


def _run(conn, step) -> None:
    with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
        step()


@pytest.fixture(params=['sqlite', 'postgresql'])
async def database(request, tmp_path):
    """Yield ``run(fn)``: execute a sync function on one transaction of a fresh database."""
    if request.param == 'sqlite':
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "policy.db"}')
        schema_name = None
    else:
        url = os.environ.get('TEST_POSTGRES_URL')
        if not url:
            pytest.skip('TEST_POSTGRES_URL not set')
        engine = create_async_engine(url)
        schema_name = f'policy_{uuid.uuid4().hex[:12]}'
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA {schema_name}'))

    async def run(fn):
        async with engine.begin() as conn:
            if schema_name:
                await conn.execute(sa.text(f'SET LOCAL search_path TO {schema_name}'))
            return await conn.run_sync(fn)

    try:
        yield run
    finally:
        if schema_name:
            async with engine.begin() as conn:
                await conn.execute(sa.text(f'DROP SCHEMA {schema_name} CASCADE'))
        await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_moves_settings_to_route_overrides_and_keeps_bots_neutral(database):
    def scenario(conn):
        _seed(conn)
        _run(conn, migration.upgrade)

        assert 'message_policy' in _columns(conn, 'bots')
        assert 'message_policy_backup' in _columns(conn, 'legacy_pipelines')

        # Existing bots: "admit everything, change nothing".
        for row in _rows(conn, 'bots').values():
            assert _value(row['message_policy']) == policy_schema.neutral_policy()

        # Messaging keeps only AI, speech and AI-specific output; the rest is backed up verbatim.
        pipelines = _rows(conn, 'legacy_pipelines')
        for pipeline_uuid, original in (('p-a', CONFIG_A), ('p-b', CONFIG_B)):
            stored = _value(pipelines[pipeline_uuid]['config'])
            backup = _value(pipelines[pipeline_uuid]['message_policy_backup'])
            assert stored == {
                'ai': original['ai'],
                'speech': original['speech'],
                'output': {'misc': {'track-function-calls': False, 'remove-think': True}},
            }
            assert backup['trigger'] == original['trigger']
            assert backup['safety'] == original['safety']
            assert policy_schema.restore_legacy_config(stored, backup) == original
        assert _value(pipelines['p-converted']['config']) == CONVERTED
        assert pipelines['p-converted']['message_policy_backup'] is None

        # One bot, several routes: each route carries the settings of its own processor.
        multi = _routes(conn, 'bot-multi')
        assert multi['r-a']['policy'] == policy_schema.split_legacy_config(CONFIG_A)[1]
        assert multi['r-b']['policy'] == policy_schema.split_legacy_config(CONFIG_B)[1]
        assert multi['r-a']['policy']['safety']['rate-limit']['limitation'] == 5
        assert multi['r-b']['policy']['output']['misc']['at-sender'] is False
        for untouched in ('r-agent', 'r-discard', 'r-converted', 'r-missing'):
            assert 'policy' not in multi[untouched]
        # Routing itself is untouched.
        assert {key: value for key, value in multi['r-a'].items() if key != 'policy'} == route('r-a', 'pipeline', 'p-a')

        # Several bots sharing one processor each get their own copy.
        shared = _routes(conn, 'bot-shared')
        assert shared['r-shared']['policy'] == multi['r-a']['policy']

        # Processor uuids are resolved inside the bot's workspace only.
        foreign = _routes(conn, 'bot-foreign')
        assert 'policy' not in foreign['r-foreign']
        assert foreign['r-own']['policy']['trigger']['group-respond-rules']['prefix'] == ['gamma']

    await database(scenario)


@pytest.mark.asyncio
async def test_migrated_route_reproduces_every_legacy_setting(database):
    def scenario(conn):
        _seed(conn)
        _run(conn, migration.upgrade)

        bot = _rows(conn, 'bots')['bot-multi']
        override = _routes(conn, 'bot-multi')['r-a']['policy']
        effective = policy_schema.resolve_policy(_value(bot['message_policy']), override)
        seen = policy_schema.overlay_policy(_value(_rows(conn, 'legacy_pipelines')['p-a']['config']), effective)

        # What stages and plugins read from the query is the legacy config again ...
        for section in ('trigger', 'safety'):
            for block, value in CONFIG_A[section].items():
                assert {key: seen[section][block][key] for key in value} == value
        for block in ('long-text-processing', 'force-delay'):
            assert seen['output'][block] == CONFIG_A['output'][block]
        for key, value in CONFIG_A['output']['misc'].items():
            assert seen['output']['misc'][key] == value
        assert seen['ai'] == CONFIG_A['ai']
        # ... with the blocks a legacy config could not switch off stated as on.
        assert seen['trigger']['group-respond-rules']['enabled'] is True
        assert seen['safety']['rate-limit']['enabled'] is True

    await database(scenario)


@pytest.mark.asyncio
async def test_upgrade_is_idempotent(database):
    def scenario(conn):
        _seed(conn)
        _run(conn, migration.upgrade)
        first = (_rows(conn, 'bots'), _rows(conn, 'legacy_pipelines'))

        _run(conn, migration.upgrade)

        assert (_rows(conn, 'bots'), _rows(conn, 'legacy_pipelines')) == first

    await database(scenario)


@pytest.mark.asyncio
async def test_downgrade_restores_configs_exactly_and_removes_policies(database):
    def scenario(conn):
        _seed(conn)
        before = (_rows(conn, 'bots'), _rows(conn, 'legacy_pipelines'))
        _run(conn, migration.upgrade)

        _run(conn, migration.downgrade)

        assert 'message_policy' not in _columns(conn, 'bots')
        assert 'message_policy_backup' not in _columns(conn, 'legacy_pipelines')
        bots, pipelines = _rows(conn, 'bots'), _rows(conn, 'legacy_pipelines')
        for pipeline_uuid in ('p-a', 'p-b', 'p-other'):
            assert _value(pipelines[pipeline_uuid]['config']) == _value(before[1][pipeline_uuid]['config'])
        for bot_uuid, row in before[0].items():
            assert _value(bots[bot_uuid]['event_bindings']) == _value(row['event_bindings'])

        # And the round trip can be taken again.
        _run(conn, migration.upgrade)
        assert _routes(conn, 'bot-multi')['r-a']['policy'] == policy_schema.split_legacy_config(CONFIG_A)[1]

    await database(scenario)


@pytest.mark.asyncio
async def test_downgrade_gives_processors_created_after_the_upgrade_usable_settings(database):
    def scenario(conn):
        _seed(conn)
        _run(conn, migration.upgrade)
        pipelines = sa.Table('legacy_pipelines', sa.MetaData(), autoload_with=conn)
        bots = sa.Table('bots', sa.MetaData(), autoload_with=conn)
        conn.execute(
            pipelines.insert(),
            [
                {'uuid': 'p-new-routed', 'workspace_uuid': 'ws-1', 'config': copy.deepcopy(CONVERTED)},
                {'uuid': 'p-new-unrouted', 'workspace_uuid': 'ws-1', 'config': copy.deepcopy(CONVERTED)},
            ],
        )
        # A bot created after the upgrade: its own policy, a route with a partial override.
        conn.execute(
            bots.insert().values(
                uuid='bot-new',
                workspace_uuid='ws-1',
                message_policy=policy_schema.default_policy(),
                event_bindings=[
                    {
                        **route('r-new', 'pipeline', 'p-new-routed'),
                        'policy': {'trigger': {'group-respond-rules': {'enabled': False}}},
                    }
                ],
            )
        )

        _run(conn, migration.downgrade)

        configs = {key: _value(row['config']) for key, row in _rows(conn, 'legacy_pipelines').items()}
        routed = configs['p-new-routed']
        # Bot default + route override, expressed in the legacy keys alone.
        assert routed['ai'] == CONVERTED['ai']
        assert routed['trigger']['group-respond-rules'] == {'at': True, 'prefix': ['ai'], 'regexp': [], 'random': 1.0}
        assert routed['safety']['rate-limit'] == {'window-length': 60, 'limitation': 60, 'strategy': 'drop'}
        assert routed['output']['misc']['remove-think'] is False
        assert routed['output']['misc']['at-sender'] is True
        # Nothing routes to it: the defaults a new processor used to get.
        unrouted = configs['p-new-unrouted']
        assert unrouted['trigger']['group-respond-rules'] == {'at': True, 'prefix': ['ai'], 'regexp': [], 'random': 0.0}
        assert unrouted['safety']['content-filter'] == {'scope': 'all', 'check-sensitive-words': True}
        # Processors that had a backup still get exactly what they had.
        assert configs['p-a'] == CONFIG_A
        assert 'policy' not in _routes(conn, 'bot-new')['r-new']

    await database(scenario)


@pytest.mark.asyncio
async def test_bindings_and_configs_stored_as_text_are_migrated(database):
    def scenario(conn):
        metadata = sa.MetaData()
        bots = sa.Table(
            'bots',
            metadata,
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('event_bindings', sa.JSON(), nullable=False),
        )
        pipelines = sa.Table(
            'legacy_pipelines',
            metadata,
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('config', sa.JSON(), nullable=False),
        )
        metadata.create_all(conn)
        # Double-encoded JSON, as older writers left it.
        conn.execute(pipelines.insert().values(uuid='p-a', workspace_uuid='ws-1', config=json.dumps(CONFIG_A)))
        conn.execute(
            bots.insert().values(
                uuid='bot', workspace_uuid='ws-1', event_bindings=json.dumps([route('r-a', 'pipeline', 'p-a')])
            )
        )

        _run(conn, migration.upgrade)

        assert _routes(conn, 'bot')['r-a']['policy'] == policy_schema.split_legacy_config(CONFIG_A)[1]
        assert 'trigger' not in _value(_rows(conn, 'legacy_pipelines')['p-a']['config'])

    await database(scenario)


@pytest.mark.asyncio
async def test_missing_tables_are_a_no_op(database):
    def scenario(conn):
        _run(conn, migration.upgrade)
        _run(conn, migration.downgrade)
        assert not sa.inspect(conn).has_table('bots')

    await database(scenario)


@pytest.mark.asyncio
async def test_partial_legacy_schemas_are_left_alone(database):
    """Fixture-sized schemas (no JSON columns, no workspace column) must not break the chain."""

    def scenario(conn):
        metadata = sa.MetaData()
        sa.Table('bots', metadata, sa.Column('uuid', sa.String(255), primary_key=True))
        sa.Table('legacy_pipelines', metadata, sa.Column('uuid', sa.String(255), primary_key=True))
        metadata.create_all(conn)

        _run(conn, migration.upgrade)
        _run(conn, migration.downgrade)

        assert _columns(conn, 'bots') == {'uuid'}
        assert _columns(conn, 'legacy_pipelines') == {'uuid'}

    await database(scenario)


@pytest.mark.asyncio
async def test_installations_without_a_workspace_column_are_converted(database):
    def scenario(conn):
        metadata = sa.MetaData()
        bots = sa.Table(
            'bots',
            metadata,
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('event_bindings', sa.JSON(), nullable=False),
        )
        pipelines = sa.Table(
            'legacy_pipelines',
            metadata,
            sa.Column('uuid', sa.String(255), primary_key=True),
            sa.Column('config', sa.JSON(), nullable=False),
        )
        metadata.create_all(conn)
        conn.execute(pipelines.insert().values(uuid='p-a', config=copy.deepcopy(CONFIG_A)))
        conn.execute(bots.insert().values(uuid='bot', event_bindings=[route('r-a', 'pipeline', 'p-a')]))

        _run(conn, migration.upgrade)
        assert _routes(conn, 'bot')['r-a']['policy'] == policy_schema.split_legacy_config(CONFIG_A)[1]

        _run(conn, migration.downgrade)
        assert _value(_rows(conn, 'legacy_pipelines')['p-a']['config']) == CONFIG_A

    await database(scenario)
