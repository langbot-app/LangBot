"""Upgrade real historical ORM schemas through both published migration heads.

The fixtures are DDL snapshots, not current metadata stamped as an old version.
Every ancestor migration runs before we seed branch-specific data and merge.
PostgreSQL cases use a unique task-owned schema; no existing tables are dropped.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity import persistence
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.alembic_runner import (
    get_alembic_current,
    get_alembic_head,
    run_alembic_downgrade,
    run_alembic_upgrade,
)
from langbot.pkg.utils import importutil


pytestmark = pytest.mark.integration
importutil.import_modules_in_pkg(persistence)

FIXTURES = Path(__file__).with_name('fixtures')
WORKSPACE = '41100000-0000-4000-8000-000000000001'
ACCOUNT = '41100000-0000-4000-8000-000000000002'
NOW = datetime.datetime(2026, 9, 1)


@pytest.fixture(params=['sqlite', pytest.param('postgresql', marks=pytest.mark.slow)])
async def convergence_engine(request, tmp_path):
    if request.param == 'sqlite':
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "convergence.db"}')
        try:
            yield engine
        finally:
            await engine.dispose()
        return

    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL not set')
    schema = f'lb_convergence_{uuid.uuid4().hex}'
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': f'{schema},public'}})
    try:
        async with admin.begin() as conn:
            await conn.exec_driver_sql(f'CREATE SCHEMA {schema}')
        yield engine
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        await admin.dispose()


async def _insert(conn, table_name, **values):
    table = await conn.run_sync(lambda sync: sa.Table(table_name, sa.MetaData(), autoload_with=sync))
    # Historical baseline tables predate Workspace identity and event bindings.
    await conn.execute(table.insert().values(**{key: value for key, value in values.items() if key in table.c}))


async def _seed_common(engine):
    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda sync: set(sa.inspect(sync).get_table_names()))
        await _insert(conn, 'metadata', key='instance_uuid', value='migration-convergence')
        await _insert(
            conn, 'users', uuid=ACCOUNT, user='owner@example.com', normalized_email='owner@example.com', password='hash'
        )
        if 'workspaces' in tables:
            await _insert(
                conn,
                'workspaces',
                uuid=WORKSPACE,
                instance_uuid='migration-convergence',
                name='Fixture',
                slug='fixture',
                created_by_account_uuid=ACCOUNT,
            )
            await _insert(
                conn,
                'workspace_memberships',
                uuid='41100000-0000-4000-8000-000000000003',
                workspace_uuid=WORKSPACE,
                account_uuid=ACCOUNT,
                role='owner',
                source='local',
            )
        await _insert(
            conn,
            'model_providers',
            uuid='provider-1',
            workspace_uuid=WORKSPACE,
            name='Fixture provider',
            requester='openai',
            base_url='https://fixture.invalid',
            api_keys=['fixture-key'],
        )
        await _insert(
            conn,
            'legacy_pipelines',
            uuid='pipeline-1',
            workspace_uuid=WORKSPACE,
            name='Fixture pipeline',
            description='preserve pipeline',
            for_version='4',
            is_default=True,
            stages=[],
            config={},
            extensions_preferences={},
        )
        await _insert(
            conn,
            'bots',
            uuid='bot-1',
            workspace_uuid=WORKSPACE,
            name='Fixture bot',
            description='preserve bot',
            adapter='fixture',
            adapter_config={},
            enable=False,
            use_pipeline_uuid='pipeline-1',
            event_bindings=[
                {
                    'id': 'route-1',
                    'event_pattern': 'message.*',
                    'target_type': 'pipeline',
                    'target_uuid': 'pipeline-1',
                    'enabled': True,
                }
            ],
            plugin_processors=[{'processor_uuid': 'agent-1', 'enabled': True}],
        )
        for index, bot in enumerate(('bot-1', 'bot-2')):
            await _insert(
                conn,
                'monitoring_messages',
                id=f'message-{index}',
                workspace_uuid=WORKSPACE,
                timestamp=NOW,
                bot_id=bot,
                bot_name=bot,
                pipeline_id='pipeline-1',
                pipeline_name='Fixture pipeline',
                message_content=f'preserve message {index}',
                session_id='shared-session',
                status='success',
                level='info',
                role='user',
            )
        await _insert(
            conn,
            'monitoring_sessions',
            workspace_uuid=WORKSPACE,
            session_id='shared-session',
            bot_id='bot-1',
            bot_name='bot-1',
            pipeline_id='pipeline-1',
            pipeline_name='Fixture pipeline',
            message_count=1,
            start_time=NOW,
            last_activity=NOW,
            is_active=True,
        )


async def _seed_branch_data(engine, source):
    async with engine.begin() as conn:
        if source == 'master':
            await _insert(
                conn,
                'passkey_credentials',
                uuid='41100000-0000-4000-8000-000000000004',
                account_uuid=ACCOUNT,
                name='Fixture passkey',
                credential_id='fixture-credential',
                public_key='fixture-public-key',
                sign_count=7,
                backed_up=True,
            )
            await _insert(
                conn,
                'codex_credentials',
                provider_uuid='provider-1',
                workspace_uuid=WORKSPACE,
                payload={'fixture': 'preserve-codex'},
                version=3,
                lease_until=0.0,
            )
            # Master already supports colliding bot sessions before this merge.
            await _insert(
                conn,
                'monitoring_sessions',
                workspace_uuid=WORKSPACE,
                session_id='shared-session',
                bot_id='bot-2',
                bot_name='bot-2',
                pipeline_id='pipeline-1',
                pipeline_name='Fixture pipeline',
                message_count=1,
                start_time=NOW,
                last_activity=NOW,
                is_active=True,
            )
        if source == 'beta':
            await _insert(
                conn,
                'agents',
                uuid='agent-1',
                workspace_uuid=WORKSPACE,
                name='Fixture agent',
                description='preserve agent',
                kind='event_processor',
                component_ref='fixture:Runner',
                config={'fixture': 'preserve-agent'},
                supported_event_patterns=['message.*'],
            )
            await _insert(
                conn,
                'runner_state',
                runner_id='fixture:Runner',
                binding_identity='agent-1',
                scope='bot',
                scope_key='fixture-scope',
                state_key='fixture-state',
                value_json='{"sentinel": 411}',
                bot_id='bot-1',
                workspace_id=WORKSPACE,
                created_at=NOW,
                updated_at=NOW,
            )


async def _assert_merged_schema_and_data(engine, source):
    assert await get_alembic_current(engine) == get_alembic_head()
    async with engine.connect() as conn:
        inspector_data = await conn.run_sync(
            lambda sync: {
                'tables': set(sa.inspect(sync).get_table_names()),
                'bot_columns': {c['name'] for c in sa.inspect(sync).get_columns('bots')},
                'agent_columns': {c['name'] for c in sa.inspect(sync).get_columns('agents')},
                'session_pk': sa.inspect(sync).get_pk_constraint('monitoring_sessions')['constrained_columns'],
            }
        )
        assert {'agents', 'runner_state', 'codex_credentials', 'passkey_credentials'} <= inspector_data['tables']
        assert {'event_bindings', 'plugin_processors'} <= inspector_data['bot_columns']
        assert 'enabled' not in inspector_data['agent_columns']
        assert inspector_data['session_pk'] == ['workspace_uuid', 'bot_id', 'session_id']
        assert await conn.scalar(sa.text('SELECT password FROM users')) == 'hash'
        assert await conn.scalar(sa.text('SELECT COUNT(*) FROM workspace_memberships')) == 1
        assert await conn.scalar(sa.text('SELECT name FROM model_providers')) == 'Fixture provider'
        assert await conn.scalar(sa.text('SELECT description FROM legacy_pipelines')) == 'preserve pipeline'
        assert (
            await conn.execute(sa.text('SELECT message_content FROM monitoring_messages ORDER BY id'))
        ).scalars().all() == [
            'preserve message 0',
            'preserve message 1',
        ]
        assert (
            await conn.execute(sa.text('SELECT bot_id FROM monitoring_sessions ORDER BY bot_id'))
        ).scalars().all() == [
            'bot-1',
            'bot-2',
        ]
        bots = await conn.run_sync(lambda sync: sa.Table('bots', sa.MetaData(), autoload_with=sync))
        row = (await conn.execute(sa.select(bots.c.event_bindings, bots.c.plugin_processors))).one()
        assert row.event_bindings[0]['target_uuid'] == 'pipeline-1'
        if source == 'beta':
            assert row.plugin_processors == [{'processor_uuid': 'agent-1', 'enabled': True}]
            assert await conn.scalar(sa.text('SELECT value_json FROM runner_state')) == '{"sentinel": 411}'
            assert await conn.scalar(sa.text('SELECT name FROM agents')) == 'Fixture agent'
        if source == 'master':
            assert await conn.scalar(sa.text('SELECT sign_count FROM passkey_credentials')) == 7
            credentials = await conn.run_sync(
                lambda sync: sa.Table('codex_credentials', sa.MetaData(), autoload_with=sync)
            )
            assert await conn.scalar(sa.select(credentials.c.payload)) == {'fixture': 'preserve-codex'}
        if engine.dialect.name == 'postgresql':
            rows = (
                await conn.execute(
                    sa.text(
                        'SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, '
                        'EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid '
                        "AND p.polname = 'langbot_workspace_isolation') AS policy "
                        'FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace '
                        "WHERE n.nspname = current_schema() AND c.relname IN ('agents', 'codex_credentials', 'monitoring_sessions')"
                    )
                )
            ).all()
            assert len(rows) == 3
            assert all(row.relrowsecurity and row.relforcerowsecurity and row.policy for row in rows)
        else:
            assert (await conn.exec_driver_sql('PRAGMA foreign_key_check')).all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['baseline', 'master', 'beta'])
async def test_historical_schema_and_populated_branch_upgrade(convergence_engine, source):
    engine = convergence_engine
    fixture = json.loads((FIXTURES / f'{source}_schema.json').read_text())
    async with engine.begin() as conn:
        for statement in fixture['dialects'][engine.dialect.name]:
            await conn.exec_driver_sql(statement)
    # Execute the published ancestors; never stamp an empty or current schema.
    await run_alembic_upgrade(engine, fixture['revision'])
    assert await get_alembic_current(engine) == fixture['revision']
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync: set(sa.inspect(sync).get_table_names()))
        if source == 'master':
            assert {'codex_credentials', 'passkey_credentials'} <= tables
            assert 'agents' not in tables and 'runner_state' not in tables
        elif source == 'beta':
            assert {'agents', 'runner_state'} <= tables
            assert 'codex_credentials' not in tables and 'passkey_credentials' not in tables
            assert await conn.run_sync(
                lambda sync: sa.inspect(sync).get_pk_constraint('monitoring_sessions')['constrained_columns']
            ) == ['workspace_uuid', 'session_id']
        else:
            assert 'workspaces' not in tables
    await _seed_common(engine)
    await _seed_branch_data(engine, source)
    if source == 'baseline' and engine.dialect.name == 'postgresql':
        # Match PersistenceManager's staged legacy bootstrap: expand the
        # account/resource contract before creating deferred tenant tables.
        # RLS 0011 requires those tables (including monitoring_tool_calls).
        await run_alembic_upgrade(engine, '0010_scope_resources')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    await run_alembic_upgrade(engine, 'head')
    await _assert_merged_schema_and_data(engine, source)
    await run_alembic_upgrade(engine, 'head')
    await _assert_merged_schema_and_data(engine, source)


@pytest.mark.asyncio
async def test_empty_database_startup_schema_then_real_migrations(convergence_engine):
    engine = convergence_engine
    async with engine.begin() as conn:
        assert await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names()) == []
        # This is the documented fresh-install contract: create_all precedes Alembic.
        await conn.run_sync(Base.metadata.create_all)
    await run_alembic_upgrade(engine, 'head')
    assert await get_alembic_current(engine) == get_alembic_head()


@pytest.mark.asyncio
async def test_merge_only_downgrade_preserves_both_branch_schemas(convergence_engine):
    engine = convergence_engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_alembic_upgrade(engine, 'head')
    await _seed_common(engine)
    await _seed_branch_data(engine, 'master')
    await _seed_branch_data(engine, 'beta')
    # Targeting a parent removes only the merge, leaving both parent heads.
    # A relative -1 is ambiguous at a merge point. Neither feature is reverted.
    await run_alembic_downgrade(engine, '0024_passkey_credentials')
    async with engine.connect() as conn:
        revisions = set((await conn.execute(sa.text('SELECT version_num FROM alembic_version'))).scalars())
        knowledge_columns = await conn.run_sync(
            lambda sync: {column['name'] for column in sa.inspect(sync).get_columns('knowledge_bases')}
        )
    assert revisions == {'0024_passkey_credentials', '0026_knowledge_base_drafts'}
    assert 'initialized' in knowledge_columns
    await run_alembic_upgrade(engine, 'head')
    await _assert_merged_schema_and_data(engine, 'master')
    await _assert_merged_schema_and_data(engine, 'beta')
