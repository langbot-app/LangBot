"""Tests for AgentRunner run ledger pull API authorization."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.entity.persistence import agent_run as agent_run_model
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot_plugin.api.entities.builtin.agent_runner.run_ledger import (
    AgentRun,
    AgentRunEvent,
    RunEventPage,
    RunPage,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from .conftest import make_resources


class FakeConnection:
    pass


class FakeApplication:
    def __init__(self, db_engine, admin_plugins=None, runner_registry=None):
        self.logger = MagicMock()
        self.persistence_mgr = MagicMock()
        self.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)
        self.agent_runner_registry = runner_registry
        self.instance_config = SimpleNamespace(
            data={
                'agent_runner': {
                    'admin_plugins': admin_plugins or [],
                }
            }
        )


@pytest.fixture
def session_registry(monkeypatch):
    registry = AgentRunSessionRegistry()
    monkeypatch.setattr(
        'langbot.pkg.agent.runner.session_registry._global_registry',
        registry,
    )
    return registry


@pytest.fixture
async def db_engine():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    assert agent_run_model.AgentRun.__tablename__ == 'agent_run'
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


class FakeRunnerRegistry:
    def __init__(self, runners):
        self.runners = runners
        self.calls = []

    async def list_runners(self, *, bound_plugins=None, use_cache=True):
        self.calls.append({'bound_plugins': bound_plugins, 'use_cache': use_cache})
        return self.runners


def _handler(db_engine, admin_plugins=None, runner_registry=None):
    async def fake_disconnect():
        return True

    fake_app = FakeApplication(db_engine, admin_plugins=admin_plugins, runner_registry=runner_registry)
    return RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)


async def _register_session(
    session_registry,
    *,
    run_id='run_1',
    conversation_id='conv_1',
    available_apis=None,
):
    await session_registry.register(
        run_id=run_id,
        runner_id='plugin:test/runner/default',
        query_id=None,
        plugin_identity='test/runner',
        resources=make_resources(),
        conversation_id=conversation_id,
        bot_id='bot_1',
        workspace_id='workspace_1',
        thread_id=None,
        available_apis=available_apis or {},
    )


async def _create_run(
    db_engine,
    *,
    run_id='run_1',
    conversation_id='conv_1',
    bot_id='bot_1',
    workspace_id='workspace_1',
    thread_id=None,
    plugin_identity='test/runner',
    runner_id='plugin:test/runner/default',
    available_apis=None,
):
    store = RunLedgerStore(db_engine)
    await store.create_run(
        run_id=run_id,
        event_id='evt_1',
        binding_id='binding_1',
        runner_id=runner_id,
        conversation_id=conversation_id,
        bot_id=bot_id,
        workspace_id=workspace_id,
        thread_id=thread_id,
        authorization={
            'runner_id': runner_id,
            'binding_id': 'binding_1',
            'plugin_identity': plugin_identity,
            'resources': make_resources(),
            'available_apis': available_apis or {},
            'conversation_id': conversation_id,
            'bot_id': bot_id,
            'workspace_id': workspace_id,
            'thread_id': thread_id,
            'state_policy': {'enable_state': True, 'state_scopes': ['conversation', 'actor']},
            'state_context': {},
        },
    )
    await store.append_event(
        run_id=run_id,
        sequence=1,
        event_type='message.completed',
        data={'message': {'role': 'assistant', 'content': 'ok'}},
    )


@pytest.mark.asyncio
async def test_run_get_returns_current_run(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_get': True})
    await _create_run(db_engine)
    handler = _handler(db_engine)
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]

    result = await run_get(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code == 0
    run = AgentRun.model_validate(result.data)
    assert run.run_id == 'run_1'
    assert run.status == 'running'


@pytest.mark.asyncio
async def test_run_list_rejects_cross_conversation(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_list': True})
    handler = _handler(db_engine)
    run_list = handler.actions[PluginToRuntimeAction.RUN_LIST.value]

    result = await run_list(
        {
            'run_id': 'run_1',
            'conversation_id': 'conv_other',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'not accessible' in result.message.lower()


@pytest.mark.asyncio
async def test_run_list_returns_scoped_runs(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_list': True})
    await _create_run(db_engine)
    await _create_run(db_engine, run_id='run_other', conversation_id='conv_other')
    handler = _handler(db_engine)
    run_list = handler.actions[PluginToRuntimeAction.RUN_LIST.value]

    result = await run_list(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code == 0
    page = RunPage.model_validate(result.data)
    assert [run.run_id for run in page.items] == ['run_1']


@pytest.mark.asyncio
async def test_run_events_page_returns_events(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_events_page': True})
    await _create_run(db_engine)
    handler = _handler(db_engine)
    run_events_page = handler.actions[PluginToRuntimeAction.RUN_EVENTS_PAGE.value]

    result = await run_events_page(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code == 0
    page = RunEventPage.model_validate(result.data)
    assert [item.sequence for item in page.items] == [1]
    assert page.items[0].type == 'message.completed'


@pytest.mark.asyncio
async def test_run_get_uses_persistent_authorization_after_session_expired(db_engine):
    await _create_run(db_engine, available_apis={'run_get': True})
    handler = _handler(db_engine)
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]

    result = await run_get(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code == 0
    run = AgentRun.model_validate(result.data)
    assert run.run_id == 'run_1'


@pytest.mark.asyncio
async def test_persistent_run_get_rejects_cross_scope(db_engine):
    await _create_run(db_engine, available_apis={'run_get': True})
    await _create_run(
        db_engine,
        run_id='run_other',
        conversation_id='conv_other',
        available_apis={'run_get': True},
    )
    handler = _handler(db_engine)
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]

    result = await run_get(
        {
            'run_id': 'run_1',
            'target_run_id': 'run_other',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'not accessible' in result.message.lower()


@pytest.mark.asyncio
async def test_persistent_run_get_requires_capability(db_engine):
    await _create_run(db_engine, available_apis={'run_get': False})
    handler = _handler(db_engine)
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]

    result = await run_get(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_persistent_authorization_does_not_reopen_artifact_api(db_engine):
    await _create_run(db_engine, available_apis={'artifact_metadata': True})
    handler = _handler(db_engine)
    artifact_metadata = handler.actions[PluginToRuntimeAction.ARTIFACT_METADATA.value]

    result = await artifact_metadata(
        {
            'run_id': 'run_1',
            'artifact_id': 'artifact_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'not found or expired' in result.message.lower()


@pytest.mark.asyncio
async def test_agent_run_admin_can_list_all_runs_with_own_run_session(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    await _create_run(db_engine)
    await _create_run(
        db_engine,
        run_id='run_other',
        conversation_id='conv_other',
        bot_id='bot_other',
        workspace_id='workspace_other',
        plugin_identity='other/runner',
        runner_id='plugin:other/runner/default',
        available_apis={'run_list': True},
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    run_list = handler.actions[PluginToRuntimeAction.RUN_LIST.value]

    result = await run_list(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'statuses': ['running'],
        }
    )

    assert result.code == 0
    page = RunPage.model_validate(result.data)
    assert [run.run_id for run in page.items] == ['run_other', 'run_1']


@pytest.mark.asyncio
async def test_agent_run_admin_permission_string_allows_without_run_id(db_engine):
    await _create_run(db_engine)
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': 'agent_run:admin',
            }
        ],
    )
    run_list = handler.actions[PluginToRuntimeAction.RUN_LIST.value]

    result = await run_list(
        {
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code == 0
    page = RunPage.model_validate(result.data)
    assert [run.run_id for run in page.items] == ['run_1']


@pytest.mark.asyncio
async def test_agent_run_admin_can_list_runner_registry_without_run_id(db_engine):
    runner_registry = FakeRunnerRegistry(
        [
            {
                'id': 'plugin:test/runner/default',
                'source': 'plugin',
                'plugin_author': 'test',
                'plugin_name': 'runner',
                'runner_name': 'default',
                'label': {'en_US': 'Default'},
            }
        ]
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'langbot/control',
                'permissions': ['agent_run:admin'],
            }
        ],
        runner_registry=runner_registry,
    )
    runner_list = handler.actions['runner_list']

    result = await runner_list(
        {
            'caller_plugin_identity': 'langbot/control',
            'include_plugins': ['test/runner'],
        }
    )

    assert result.code == 0
    assert result.data['items'][0]['id'] == 'plugin:test/runner/default'
    assert runner_registry.calls == [
        {
            'bound_plugins': ['test/runner'],
            'use_cache': True,
        }
    ]


@pytest.mark.asyncio
async def test_unconfigured_plugin_cannot_list_runner_registry(db_engine):
    handler = _handler(db_engine, runner_registry=FakeRunnerRegistry([]))
    runner_list = handler.actions['runner_list']

    result = await runner_list({'caller_plugin_identity': 'test/runner'})

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_agent_run_admin_can_get_and_page_cross_scope_with_own_run_session(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    await _create_run(
        db_engine,
        run_id='run_other',
        conversation_id='conv_other',
        bot_id='bot_other',
        workspace_id='workspace_other',
        plugin_identity='other/runner',
        runner_id='plugin:other/runner/default',
        available_apis={'run_get': True, 'run_events_page': True},
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]
    run_events_page = handler.actions[PluginToRuntimeAction.RUN_EVENTS_PAGE.value]

    run_result = await run_get(
        {
            'run_id': 'run_1',
            'target_run_id': 'run_other',
            'caller_plugin_identity': 'test/runner',
        }
    )
    events_result = await run_events_page(
        {
            'run_id': 'run_1',
            'target_run_id': 'run_other',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert run_result.code == 0
    assert AgentRun.model_validate(run_result.data).run_id == 'run_other'
    assert events_result.code == 0
    page = RunEventPage.model_validate(events_result.data)
    assert [event.type for event in page.items] == ['message.completed']


@pytest.mark.asyncio
async def test_agent_run_admin_can_get_and_page_cross_scope_without_run_id(db_engine):
    await _create_run(
        db_engine,
        run_id='run_other',
        conversation_id='conv_other',
        bot_id='bot_other',
        workspace_id='workspace_other',
        plugin_identity='other/runner',
        runner_id='plugin:other/runner/default',
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'langbot/control',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]
    run_events_page = handler.actions[PluginToRuntimeAction.RUN_EVENTS_PAGE.value]

    run_result = await run_get(
        {
            'target_run_id': 'run_other',
            'caller_plugin_identity': 'langbot/control',
        }
    )
    events_result = await run_events_page(
        {
            'target_run_id': 'run_other',
            'caller_plugin_identity': 'langbot/control',
        }
    )

    assert run_result.code == 0
    assert AgentRun.model_validate(run_result.data).run_id == 'run_other'
    assert events_result.code == 0
    page = RunEventPage.model_validate(events_result.data)
    assert [event.type for event in page.items] == ['message.completed']


@pytest.mark.asyncio
async def test_unconfigured_plugin_cannot_use_admin_run_actions_without_run_id(db_engine):
    await _create_run(db_engine)
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'langbot/control',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    run_list = handler.actions[PluginToRuntimeAction.RUN_LIST.value]

    result = await run_list(
        {
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'run_id is required' in result.message.lower()


@pytest.mark.asyncio
async def test_agent_run_admin_can_cancel_cross_scope_with_own_run_session(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    await _create_run(
        db_engine,
        run_id='run_other',
        conversation_id='conv_other',
        bot_id='bot_other',
        workspace_id='workspace_other',
        plugin_identity='other/runner',
        runner_id='plugin:other/runner/default',
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    run_cancel = handler.actions[PluginToRuntimeAction.RUN_CANCEL.value]

    result = await run_cancel(
        {
            'run_id': 'run_1',
            'target_run_id': 'run_other',
            'caller_plugin_identity': 'test/runner',
            'reason': 'admin requested',
        }
    )

    assert result.code == 0
    run = AgentRun.model_validate(result.data)
    assert run.run_id == 'run_other'
    assert run.cancel_requested_at is not None
    assert run.status_reason == 'admin requested'
    events, _next_cursor, _prev_cursor, _has_more = await RunLedgerStore(db_engine).page_run_events(
        run_id='run_other',
    )
    assert [event['type'] for event in events] == ['message.completed', 'admin.run_cancel']
    assert events[1]['source'] == 'host'
    assert events[1]['data']['caller_plugin_identity'] == 'test/runner'
    assert events[1]['metadata'] == {'permission': 'agent_run:admin'}


@pytest.mark.asyncio
async def test_configured_admin_identity_cannot_be_spoofed_with_other_run_session(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    await _create_run(db_engine)
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'langbot/control',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]

    result = await run_get(
        {
            'run_id': 'run_1',
            'target_run_id': 'run_1',
            'caller_plugin_identity': 'langbot/control',
        }
    )

    assert result.code != 0
    assert 'mismatch' in result.message.lower()


@pytest.mark.asyncio
async def test_agent_run_admin_permission_does_not_grant_runtime_admin(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': ['agent_run:admin'],
            }
        ],
    )
    runtime_list = handler.actions[PluginToRuntimeAction.RUNTIME_LIST.value]

    result = await runtime_list(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_runtime_admin_can_register_list_and_claim_with_own_run_session(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    await RunLedgerStore(db_engine).create_run(
        run_id='queued_run',
        event_id='evt_queued',
        binding_id='binding_1',
        runner_id='plugin:other/runner/default',
        conversation_id='conv_1',
        bot_id='bot_1',
        workspace_id='workspace_1',
        status='queued',
        queue_name='default',
        priority=5,
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': ['runtime:admin'],
            }
        ],
    )
    runtime_register = handler.actions[PluginToRuntimeAction.RUNTIME_REGISTER.value]
    runtime_list = handler.actions[PluginToRuntimeAction.RUNTIME_LIST.value]
    run_claim = handler.actions[PluginToRuntimeAction.RUN_CLAIM.value]

    registered = await runtime_register(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'display_name': 'Runtime 1',
            'labels': {'region': 'test'},
        }
    )
    page = await runtime_list(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'statuses': ['online'],
            'labels': {'region': 'test'},
        }
    )
    claimed = await run_claim(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'queue_name': 'default',
            'runner_ids': ['plugin:other/runner/default'],
        }
    )

    assert registered.code == 0
    assert registered.data['runtime_id'] == 'runtime_1'
    assert page.code == 0
    assert [item['runtime_id'] for item in page.data['items']] == ['runtime_1']
    assert claimed.code == 0
    assert claimed.data['run_id'] == 'queued_run'
    assert claimed.data['claimed_by_runtime_id'] == 'runtime_1'


@pytest.mark.asyncio
async def test_runtime_admin_can_register_list_and_claim_without_run_id(db_engine):
    await RunLedgerStore(db_engine).create_run(
        run_id='queued_run',
        event_id='evt_queued',
        binding_id='binding_1',
        runner_id='plugin:other/runner/default',
        conversation_id='conv_1',
        bot_id='bot_1',
        workspace_id='workspace_1',
        status='queued',
        queue_name='default',
        priority=5,
    )
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'langbot/control',
                'permissions': ['runtime:admin'],
            }
        ],
    )
    runtime_register = handler.actions[PluginToRuntimeAction.RUNTIME_REGISTER.value]
    runtime_list = handler.actions[PluginToRuntimeAction.RUNTIME_LIST.value]
    run_claim = handler.actions[PluginToRuntimeAction.RUN_CLAIM.value]

    registered = await runtime_register(
        {
            'caller_plugin_identity': 'langbot/control',
            'runtime_id': 'runtime_1',
            'display_name': 'Runtime 1',
            'labels': {'region': 'test'},
        }
    )
    page = await runtime_list(
        {
            'caller_plugin_identity': 'langbot/control',
            'statuses': ['online'],
            'labels': {'region': 'test'},
        }
    )
    claimed = await run_claim(
        {
            'caller_plugin_identity': 'langbot/control',
            'runtime_id': 'runtime_1',
            'queue_name': 'default',
            'runner_ids': ['plugin:other/runner/default'],
        }
    )

    assert registered.code == 0
    assert registered.data['runtime_id'] == 'runtime_1'
    assert page.code == 0
    assert [item['runtime_id'] for item in page.data['items']] == ['runtime_1']
    assert claimed.code == 0
    assert claimed.data['run_id'] == 'queued_run'
    assert claimed.data['claimed_by_runtime_id'] == 'runtime_1'


@pytest.mark.asyncio
async def test_runtime_admin_can_reconcile_without_run_id(db_engine):
    store = RunLedgerStore(db_engine)
    await store.register_runtime(
        runtime_id='runtime_stale',
        display_name='Runtime Stale',
        heartbeat_deadline_seconds=60,
    )
    await store.create_run(
        run_id='claimed_run',
        event_id='evt_claimed',
        binding_id='binding_1',
        runner_id='plugin:other/runner/default',
        status='queued',
        queue_name='default',
    )
    claim = await store.claim_next_run(runtime_id='runtime_stale', queue_name='default', lease_seconds=60)
    assert claim is not None

    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    expired_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    async with session_factory() as session:
        await session.execute(
            sqlalchemy.update(agent_run_model.AgentRun)
            .where(agent_run_model.AgentRun.run_id == 'claimed_run')
            .values(claim_lease_expires_at=expired_at)
        )
        await session.execute(
            sqlalchemy.update(agent_run_model.AgentRuntime)
            .where(agent_run_model.AgentRuntime.runtime_id == 'runtime_stale')
            .values(
                last_heartbeat_at=expired_at,
                heartbeat_deadline_at=expired_at,
            )
        )
        await session.commit()

    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'langbot/control',
                'permissions': ['runtime:admin'],
            }
        ],
    )
    runtime_reconcile = handler.actions['runtime_reconcile']

    result = await runtime_reconcile({'caller_plugin_identity': 'langbot/control'})

    assert result.code == 0
    assert result.data['stale_count'] == 1
    assert result.data['released_claim_count'] == 1
    assert result.data['stale_runtimes'][0]['runtime_id'] == 'runtime_stale'
    assert result.data['released_claims'][0]['run_id'] == 'claimed_run'
    assert (await store.get_runtime('runtime_stale'))['status'] == 'stale'
    released_run = await store.get_run('claimed_run')
    assert released_run is not None
    assert released_run['status'] == 'queued'
    assert released_run['claimed_by_runtime_id'] is None
    assert released_run['claim_token'] is None


@pytest.mark.asyncio
async def test_unconfigured_plugin_cannot_reconcile_runtime(db_engine):
    handler = _handler(db_engine)
    runtime_reconcile = handler.actions['runtime_reconcile']

    result = await runtime_reconcile({'caller_plugin_identity': 'test/runner'})

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_disabled_admin_plugin_entry_does_not_grant_access(session_registry, db_engine):
    await _register_session(session_registry, available_apis={})
    await _create_run(db_engine)
    handler = _handler(
        db_engine,
        admin_plugins=[
            {
                'identity': 'test/runner',
                'permissions': ['agent_run:admin', 'runtime:admin'],
                'enabled': False,
            }
        ],
    )
    run_get = handler.actions[PluginToRuntimeAction.RUN_GET.value]

    result = await run_get(
        {
            'run_id': 'run_1',
            'target_run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
        }
    )

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_run_cancel_basic_path(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_cancel': True})
    await _create_run(db_engine)
    handler = _handler(db_engine)
    run_cancel = handler.actions[PluginToRuntimeAction.RUN_CANCEL.value]

    result = await run_cancel(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'reason': 'user requested',
        }
    )

    assert result.code == 0
    run = AgentRun.model_validate(result.data)
    assert run.run_id == 'run_1'
    assert run.cancel_requested_at is not None
    assert run.status_reason == 'user requested'


@pytest.mark.asyncio
async def test_run_append_result_basic_path(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_append_result': True})
    await _create_run(db_engine)
    handler = _handler(db_engine)
    run_append_result = handler.actions[PluginToRuntimeAction.RUN_APPEND_RESULT.value]

    result = await run_append_result(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'sequence': 2,
            'result': {
                'type': 'message.delta',
                'data': {'delta': 'hello'},
                'usage': {'output_tokens': 1},
            },
        }
    )

    assert result.code == 0
    event = AgentRunEvent.model_validate(result.data)
    assert event.run_id == 'run_1'
    assert event.sequence == 2
    assert event.type == 'message.delta'
    assert event.data == {'delta': 'hello'}
    assert event.usage == {'output_tokens': 1}


@pytest.mark.asyncio
async def test_run_finalize_basic_path(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'run_finalize': True})
    await _create_run(db_engine)
    handler = _handler(db_engine)
    run_finalize = handler.actions[PluginToRuntimeAction.RUN_FINALIZE.value]

    result = await run_finalize(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'status': 'completed',
            'status_reason': 'done',
            'usage': {'total_tokens': 3},
        }
    )

    assert result.code == 0
    run = AgentRun.model_validate(result.data)
    assert run.status == 'completed'
    assert run.status_reason == 'done'
    assert run.finished_at is not None
    assert run.usage == {'total_tokens': 3}


@pytest.mark.asyncio
async def test_runtime_register_heartbeat_and_list_actions(session_registry, db_engine):
    await _register_session(
        session_registry,
        available_apis={
            'runtime_register': True,
            'runtime_heartbeat': True,
            'runtime_list': True,
        },
    )
    handler = _handler(db_engine)
    runtime_register = handler.actions[PluginToRuntimeAction.RUNTIME_REGISTER.value]
    runtime_heartbeat = handler.actions[PluginToRuntimeAction.RUNTIME_HEARTBEAT.value]
    runtime_list = handler.actions[PluginToRuntimeAction.RUNTIME_LIST.value]

    registered = await runtime_register(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'display_name': 'Runtime 1',
            'capabilities': {'runner': True},
            'labels': {'region': 'test'},
            'metadata': {'slots': 2},
        }
    )

    assert registered.code == 0
    assert registered.data['runtime_id'] == 'runtime_1'
    assert registered.data['capabilities'] == {'runner': True}

    heartbeat = await runtime_heartbeat(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'capabilities': {'runner': True, 'stream': True},
            'labels': {'region': 'test'},
            'metadata': {'active_runs': 1},
        }
    )

    assert heartbeat.code == 0
    assert heartbeat.data['capabilities'] == {'runner': True, 'stream': True}
    assert heartbeat.data['metadata'] == {'slots': 2, 'active_runs': 1}

    page = await runtime_list(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'statuses': ['online'],
            'labels': {'region': 'test'},
        }
    )

    assert page.code == 0
    assert [item['runtime_id'] for item in page.data['items']] == ['runtime_1']


@pytest.mark.asyncio
async def test_run_claim_renew_and_release_actions(session_registry, db_engine):
    await _register_session(
        session_registry,
        available_apis={
            'run_claim': True,
            'run_renew_claim': True,
            'run_release_claim': True,
        },
    )
    await RunLedgerStore(db_engine).create_run(
        run_id='queued_run',
        event_id='evt_queued',
        binding_id='binding_1',
        runner_id='plugin:test/runner/default',
        conversation_id='conv_1',
        bot_id='bot_1',
        workspace_id='workspace_1',
        status='queued',
        queue_name='default',
        priority=5,
    )
    handler = _handler(db_engine)
    run_claim = handler.actions[PluginToRuntimeAction.RUN_CLAIM.value]
    run_renew_claim = handler.actions[PluginToRuntimeAction.RUN_RENEW_CLAIM.value]
    run_release_claim = handler.actions[PluginToRuntimeAction.RUN_RELEASE_CLAIM.value]

    claimed = await run_claim(
        {
            'run_id': 'run_1',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'queue_name': 'default',
            'lease_seconds': 30,
        }
    )

    assert claimed.code == 0
    assert claimed.data['run_id'] == 'queued_run'
    assert claimed.data['status'] == 'claimed'
    assert claimed.data['claimed_by_runtime_id'] == 'runtime_1'
    claim_token = claimed.data['claim_token']

    renewed = await run_renew_claim(
        {
            'run_id': 'run_1',
            'target_run_id': 'queued_run',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'claim_token': claim_token,
            'lease_seconds': 60,
        }
    )

    assert renewed.code == 0
    assert renewed.data['claim_token'] == claim_token

    released = await run_release_claim(
        {
            'run_id': 'run_1',
            'target_run_id': 'queued_run',
            'caller_plugin_identity': 'test/runner',
            'runtime_id': 'runtime_1',
            'claim_token': claim_token,
            'reason': 'done with lease',
        }
    )

    assert released.code == 0
    assert released.data['status'] == 'queued'
    assert released.data['claimed_by_runtime_id'] is None
    assert released.data['claim_token'] is None
