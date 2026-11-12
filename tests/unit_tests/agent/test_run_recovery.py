"""Durable steering and Host retry/resume acceptance tests."""

import time
import sys
from pathlib import Path
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from langbot.pkg.agent.runner.event_log_store import EventLogStore
from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.agent.runner.run_journal import AgentRunJournal
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.plugin import agent_state_actions
from tests.unit_tests.agent.conftest import make_resources
from tests.unit_tests.agent.test_orchestrator_integration import (
    FakeApplication,
    FakePluginConnector,
    FakeRegistry,
    make_descriptor,
    make_query,
)
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from langbot.pkg.core.taskmgr import AsyncTaskManager


@pytest.fixture
async def clean_agent_state(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.agent.runner.persistent_state_store import reset_persistent_state_store

    registry = get_session_registry()
    reset_persistent_state_store()
    # Recovery reads and the background worker must not share one in-memory connection.
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "lifecycle.sqlite"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        for session in await registry.list_active_runs():
            await registry.unregister(session['run_id'])
        reset_persistent_state_store()
        await engine.dispose()


class ActionHost:
    def __init__(self, engine):
        self.actions = {}
        self.ap = SimpleNamespace(
            logger=Mock(),
            persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine),
        )
        agent_state_actions.register(self)

    def action(self, name):
        def register(fn):
            self.actions[name.value] = fn
            return fn

        return register


def secured_host(ap, *, workspace_id, plugin_identity):
    from langbot_plugin.entities.io.context import InstallationBinding
    from langbot.pkg.entity.persistence.plugin import PluginSetting
    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    binding = InstallationBinding(
        instance_uuid='instance-test',
        workspace_uuid=workspace_id,
        placement_generation=1,
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    author, name = plugin_identity.split('/')
    setting = PluginSetting(
        workspace_uuid=workspace_id,
        installation_uuid=binding.installation_uuid,
        plugin_author=author,
        plugin_name=name,
        enabled=True,
        runtime_revision=1,
        artifact_digest=binding.artifact_digest,
        permission_declaration={'workspace_operations': [], 'capabilities': []},
        permission_grants={'workspace_operations': [], 'capabilities': []},
    )
    ap.persistence_mgr.execute_async = AsyncMock(return_value=Mock(first=Mock(return_value=(setting,))))
    ap.workspace_service = SimpleNamespace(get_execution_binding=AsyncMock(return_value=binding))
    host = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), ap)
    host.register_installation_binding(binding, plugin_author=author, plugin_name=name)
    return host, binding


async def setup_steering(engine, run_id='run'):
    registry = get_session_registry()
    await registry.register(
        run_id=run_id,
        runner_id='plugin:test/runner/default',
        query_id=1,
        plugin_identity='test/runner',
        resources=make_resources(),
        available_apis={'steering_pull': True, 'steering_ack': True},
        conversation_id='conv',
        bot_id='bot',
        workspace_id='ws',
    )
    item = {
        'claimed_run_id': run_id,
        'runner_id': 'plugin:test/runner/default',
        'event': {'event_id': 'followup', 'event_type': 'message.received', 'source': 'platform'},
        'input': {'text': 'apply this follow-up once'},
        'conversation': {'conversation_id': 'conv', 'bot_id': 'bot', 'workspace_id': 'ws'},
    }
    await registry.enqueue_steering(run_id, item)
    store = EventLogStore(engine)
    await store.append_event(
        event_id='followup',
        event_type='message.received',
        source='platform',
        conversation_id='conv',
        bot_id='bot',
        workspace_id='ws',
        run_id=run_id,
        runner_id='plugin:test/runner/default',
        input_json=item['input'],
        metadata={'steering': {'status': 'queued'}},
    )
    return registry, store, ActionHost(engine)


def pending_args():
    return dict(conversation_id='conv', runner_id='plugin:test/runner/default', bot_id='bot', workspace_id='ws')


@pytest.mark.asyncio
async def test_old_client_pull_is_not_replayed_after_success(clean_agent_state):
    registry, store, h = await setup_steering(clean_agent_state)
    # Actual old SDK/plugin request: no claim flag and no acknowledgement API.
    response = await h.actions['steering_pull']({'run_id': 'run', 'caller_plugin_identity': 'test/runner'})
    assert response.code == 0 and len(response.data['items']) == 1
    session = await registry.unregister('run')
    await AgentRunJournal(h.ap).write_steering_dropped_audits(
        session['steering_queue'], 'run', 'plugin:test/runner/default'
    )
    pending = await store.list_pending_steering(**pending_args())
    assert pending == [], 'Successful old-client input is queued again for the next run'


@pytest.mark.asyncio
async def test_recovery_finds_pending_after_200_completed_inputs(clean_agent_state):
    store = EventLogStore(clean_agent_state)
    for n in range(201):
        await store.append_event(
            event_id=f'event-{n}',
            event_type='message.received',
            source='platform',
            conversation_id='conv',
            bot_id='bot',
            workspace_id='ws',
            runner_id='plugin:test/runner/default',
            metadata={'steering': {'status': 'acknowledged' if n < 200 else 'queued'}},
        )
    pending = await store.list_pending_steering(**pending_args())
    assert [row['event_id'] for row in pending] == ['event-200']


@pytest.mark.asyncio
async def test_ack_is_durable_before_success_and_can_be_retried(clean_agent_state, monkeypatch):
    registry, store, h = await setup_steering(clean_agent_state)
    args = {'run_id': 'run', 'caller_plugin_identity': 'test/runner'}
    response = await h.actions['steering_pull']({**args, 'claim': True})
    delivery_id = response.data['items'][0]['delivery_id']
    original = EventLogStore.acknowledge_steering_deliveries

    async def database_unavailable(*a, **kw):
        raise RuntimeError('injected database write failure')

    monkeypatch.setattr(EventLogStore, 'acknowledge_steering_deliveries', database_unavailable)
    first = await h.actions['steering_ack']({**args, 'delivery_ids': [delivery_id]})
    assert first.code != 0
    monkeypatch.setattr(EventLogStore, 'acknowledge_steering_deliveries', original)
    second = await h.actions['steering_ack']({**args, 'delivery_ids': [delivery_id]})
    pending = await store.list_pending_steering(**pending_args())
    assert pending == [], (
        f'ACK responses first={first.model_dump()} second={second.model_dump()}, '
        f'but durable pending={[r["event_id"] for r in pending]}'
    )


@pytest.mark.asyncio
async def test_repeated_ack_does_not_requeue_durably_acknowledged_input(clean_agent_state):
    registry, store, h = await setup_steering(clean_agent_state)
    args = {'run_id': 'run', 'caller_plugin_identity': 'test/runner'}
    response = await h.actions['steering_pull']({**args, 'claim': True})
    delivery_id = response.data['items'][0]['delivery_id']
    await h.actions['steering_ack']({**args, 'delivery_ids': [delivery_id]})
    second = await h.actions['steering_ack']({**args, 'delivery_ids': [delivery_id]})
    assert second.code == 0
    assert await store.list_pending_steering(**pending_args()) == []


@pytest.mark.asyncio
async def test_cancelled_result_retains_cleanup_ack_in_history(clean_agent_state):
    connector = FakePluginConnector(
        results=[{'type': 'run.cancelled', 'data': {'reason': 'stop', 'cleanup_confirmed': True}}]
    )
    ap = FakeApplication(connector, clean_agent_state)
    runner = AgentRunOrchestrator(ap, FakeRegistry(make_descriptor()))
    assert [message async for message in runner.run_from_query(make_query())] == []
    run = await RunLedgerStore(clean_agent_state).get_run(connector.contexts[0]['run_id'])
    assert run['status'] == 'cancelled'
    events, *_ = await RunLedgerStore(clean_agent_state).page_run_events(run_id=run['run_id'])
    assert events[0]['data']['cleanup_confirmed'] is True


@pytest.mark.asyncio
async def test_external_queue_retry_clears_expired_deadline(clean_agent_state):
    store = RunLedgerStore(clean_agent_state)
    expired = int(time.time()) - 60
    await store.create_run(
        run_id='expired', event_id='event', binding_id='binding', runner_id='runner', deadline_at=expired
    )
    await store.finalize_run(run_id='expired', status='timeout')
    retried = await store.retry_run(run_id='expired')
    assert retried['status'] == 'queued'
    assert retried['deadline_at'] is None


@pytest.mark.asyncio
async def test_usage_survives_disconnect(clean_agent_state):
    connector = FakePluginConnector()

    async def run_runner(**kwargs):
        connector.contexts.append(kwargs['context'])
        yield {
            'type': 'run.progress',
            'data': {'progress': 50},
            'usage': {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10},
        }
        raise ConnectionError('injected transport disconnect')

    connector.run_runner = run_runner
    ap = FakeApplication(connector, clean_agent_state)
    runner = AgentRunOrchestrator(ap, FakeRegistry(make_descriptor()))
    with pytest.raises(Exception):
        async for _ in runner.run_from_query(make_query()):
            pass
    run = await RunLedgerStore(clean_agent_state).get_run(connector.contexts[0]['run_id'])
    assert run['status'] == 'failed'
    assert run['usage']['total_tokens'] == 10


@pytest.mark.asyncio
async def test_recovery_does_not_deliver_same_input_to_two_active_runs(clean_agent_state):
    registry, store, h = await setup_steering(clean_agent_state, run_id='dead-source')
    await registry.unregister('dead-source')
    descriptor = make_descriptor()
    descriptor.capabilities.steering = True
    # Recovery queries exactly the descriptor's runner id.
    descriptor.id = 'plugin:test/runner/default'
    event = AgentEventEnvelope(
        event_id='new-event',
        event_type='message.received',
        source='platform',
        conversation_id='conv',
        bot_id='bot',
        workspace_id='ws',
        input={'text': 'new request'},
        delivery={'surface': 'test'},
    )
    orchestrator = AgentRunOrchestrator(h.ap, FakeRegistry(descriptor))
    for run_id in ['new-A', 'new-B']:
        await registry.register(
            run_id=run_id,
            runner_id=descriptor.id,
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
        )
        recovered = await orchestrator._load_recoverable_steering(event=event, descriptor=descriptor, run_id=run_id)
        await registry.restore_steering(run_id, recovered)
    first = await registry.pull_steering('new-A', claim=True)
    second = await registry.pull_steering('new-B', claim=True)
    assert len(first) + len(second) == 1, [item['event']['event_id'] for item in first + second]


@pytest.mark.asyncio
@pytest.mark.parametrize('leased', [False, True])
async def test_actual_localagent_and_sdk_do_not_replay_processed_followup(clean_agent_state, leased):
    from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
    from langbot_plugin.api.proxies.runner import RunnerAPIProxy

    localagent = Path(__file__).resolve().parents[3] / 'plugins/Runner/LocalAgent'
    sys.path.insert(0, str(localagent))
    from pkg.agent_core.langbot import LangBotSteeringPuller

    registry, store, h = await setup_steering(clean_agent_state)
    h, binding = secured_host(h.ap, workspace_id='ws', plugin_identity='test/runner')

    class CoreActionBridge:
        async def call_action(self, action, data, timeout=15, **kwargs):
            token = h._current_action_context.set(binding)
            try:
                response = await h.actions[action.value](data)
            finally:
                h._current_action_context.reset(token)
            assert response.code == 0, response.message
            return response.data

    ctx = RunnerContext.model_validate(
        {
            'run_id': 'run',
            'trigger': {'type': 'message.received'},
            'event': {'event_id': 'trigger', 'event_type': 'message.received', 'source': 'platform'},
            'input': {'text': 'hi'},
            'delivery': {'surface': 'test'},
            'runtime': {},
            'context': {'available_apis': {'steering_pull': True, 'steering_ack': leased}},
            'resources': make_resources(),
        }
    )
    proxy = RunnerAPIProxy(ctx, CoreActionBridge())
    puller = LangBotSteeringPuller(proxy)
    messages = await puller.pull_messages()
    assert len(messages) == 1 and messages[0].content == 'apply this follow-up once'
    session = await registry.unregister('run')
    await AgentRunJournal(h.ap).write_steering_dropped_audits(
        session['steering_queue'], 'run', 'plugin:test/runner/default'
    )
    pending = await store.list_pending_steering(**pending_args())
    assert pending == [], 'Actual LocalAgent + new SDK leaves the consumed message queued again'


@pytest.mark.asyncio
@pytest.mark.parametrize('authorized', [False, True])
async def test_secured_steering_ack_checks_persistent_authorization(clean_agent_state, authorized):
    registry, store, host = await setup_steering(clean_agent_state)
    host, binding = secured_host(host.ap, workspace_id='ws', plugin_identity='test/runner')
    token = host._current_action_context.set(binding)
    try:
        pulled = await host.actions['steering_pull']({'run_id': 'run', 'claim': True})
        assert pulled.code == 0, pulled.message
        delivery_id = pulled.data['items'][0]['delivery_id']
        await registry.unregister('run')
        authorization = {
            'workspace_id': 'ws',
            'conversation_id': 'conv',
            'plugin_identity': 'test/runner',
            'available_apis': {'steering_ack': authorized},
        }
        ledger = RunLedgerStore(clean_agent_state)
        await ledger.create_run(
            run_id='run',
            event_id='trigger',
            binding_id='binding',
            runner_id='plugin:test/runner/default',
            workspace_id='ws',
            deadline_at=time.time() - 1,
            authorization=authorization,
        )
        await ledger.finalize_run(run_id='run', status='cancelled')
        response = await host.actions['steering_ack']({'run_id': 'run', 'delivery_ids': [delivery_id]})
        if authorized:
            assert response.code == 0, response.message
            assert response.data == {'acknowledged': [delivery_id], 'unknown': []}
            assert await store.list_pending_steering(**pending_args()) == []
        else:
            assert response.code != 0 and 'not authorized' in response.message
    finally:
        host._current_action_context.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize('resume', [False, True])
@pytest.mark.parametrize('platform', ['telegram', 'discord'])
@pytest.mark.parametrize('quote_origin', [False, True])
async def test_sdk_recovery_dispatches_new_attempt_and_preserves_source(
    clean_agent_state, resume, platform, quote_origin
):
    from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
    from langbot_plugin.api.proxies.runner import RunnerAPIProxy

    if not hasattr(RunnerAPIProxy, 'run_retry'):
        pytest.skip('Requires the in-tree lifecycle SDK')

    descriptor = make_descriptor()
    descriptor.raw_manifest = {'metadata': {'supports_resume': True}}
    connector = FakePluginConnector(
        results=[
            {'type': 'tool.call.started', 'data': {'tool_call_id': 'done', 'tool_name': 'fixture', 'parameters': {}}},
            {
                'type': 'tool.call.completed',
                'data': {'tool_call_id': 'done', 'tool_name': 'fixture', 'result': {'done': True}},
            },
            {'type': 'run.failed', 'data': {'error': 'interrupted', 'retryable': True}},
        ]
    )
    ap = FakeApplication(connector, clean_agent_state)
    ap.logger = Mock()
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
    ap.agent_run_orchestrator = orchestrator
    from langbot_plugin.api.entities.builtin.platform import events, entities, message
    from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

    query = make_query()
    query.launcher_type = LauncherTypes.GROUP
    query.launcher_id = '-100#77' if platform == 'telegram' else '789'
    query.sender_id = '456'
    query.session.launcher_type = query.launcher_type
    query.session.launcher_id = query.launcher_id
    query.session.sender_id = query.sender_id
    query.message_chain = message.MessageChain(
        [message.Source(id='10', time=query.message_chain[0].time), message.Plain(text='hello')]
    )
    query.message_event = events.MessageReceivedEvent(
        message_id='10',
        sender=entities.User(id='456'),
        chat_type='group',
        chat_id=query.launcher_id,
        message_chain=query.message_chain,
    ).to_legacy_event()
    if platform == 'telegram':
        from tests.unit_tests.platform.test_telegram_eba_adapter import make_adapter

        adapter = make_adapter()
        transport = AsyncMock(return_value=SimpleNamespace(message_id=91))
        adapter.bot = SimpleNamespace(send_message=transport)
    else:
        from tests.unit_tests.platform.test_discord_eba_adapter import make_adapter

        adapter = make_adapter()
        transport = AsyncMock(return_value=SimpleNamespace(id=91))
        channel = SimpleNamespace(id=789, send=transport)
        adapter.bot = SimpleNamespace(get_guild=Mock(return_value=None), get_channel=Mock(return_value=channel))
        query.message_event.source_platform_object = SimpleNamespace(channel=channel)
    query.adapter = adapter
    with pytest.raises(Exception, match='interrupted'):
        async for _ in orchestrator.run_from_query(query):
            pass
    source_context = connector.contexts[0]
    source_id = source_context['run_id']
    await RunLedgerStore(clean_agent_state).finalize_run(
        run_id=source_id,
        status='failed',
        metadata={
            'processor_id': 'untrusted-processor',
            'processor_type': 'event_processor',
            'replay_event': {'input': {'text': 'untrusted replacement'}},
        },
    )
    ap.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-test', workspace_uuid='workspace-test', placement_generation=1
            )
        )
    )
    config = query.pipeline_config
    config['safety'] = {'content-filter': {'check-sensitive-words': True, 'scope': 'output-msg'}}
    config['output'] = {
        'force-delay': {'min': 0, 'max': 0},
        'misc': {'at-sender': True, 'quote-origin': quote_origin, 'track-function-calls': False},
    }
    ap.pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={
                'uuid': 'pipeline_001',
                'workspace_uuid': 'workspace-test',
                'name': 'Recovery contract',
                'config': config,
                'stages': ['MessageProcessor', 'PostContentFilterStage', 'ResponseWrapper', 'SendResponseBackStage'],
                'extensions_preferences': {
                    'enable_all_skills': False,
                    'skills': ['demo'],
                    'enable_all_plugins': False,
                    'plugins': [{'author': 'langbot-team', 'name': 'LocalAgent'}],
                    'workspace_operations': ['pipeline.list'],
                    'allowed_platform_tools': ['platform_send_message'],
                },
            }
        )
    )
    ap.tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=[]))
    ap.bot_mgr = SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter)))
    ap.platform_mgr = ap.bot_mgr
    from langbot.pkg.pipeline.pipelinemgr import PipelineManager
    from langbot.pkg.pipeline.stage import PipelineStage
    from langbot.pkg.pipeline.cntfilter.cntfilter import ContentFilterStage
    from langbot.pkg.pipeline.wrapper.wrapper import ResponseWrapper
    from langbot.pkg.pipeline.respback.respback import SendResponseBackStage
    from langbot_plugin.api.entities.context import EventContext

    class UnusedProcessor(PipelineStage):
        async def process(self, query, stage_name):
            raise AssertionError('Recovery must not execute the MessageProcessor twice')

    ap.pipeline_mgr = PipelineManager(ap)
    ap.pipeline_mgr.stage_dict = {
        'MessageProcessor': UnusedProcessor,
        'PostContentFilterStage': ContentFilterStage,
        'ResponseWrapper': ResponseWrapper,
        'SendResponseBackStage': SendResponseBackStage,
    }
    ap.sensitive_meta = SimpleNamespace(data={'words': ['recovered'], 'mask': '*', 'mask_word': 'MASKED'})
    ap.sess_mgr = SimpleNamespace(get_session=AsyncMock(side_effect=lambda execution_query: execution_query.session))

    async def emit_event(event, bound_plugins):
        assert bound_plugins == ['langbot-team/LocalAgent']
        assert event.response_text == 'MASKED'
        event.reply_message_chain = message.MessageChain([message.Plain(text='wrapped:' + event.response_text)])
        return EventContext.from_event(event)

    connector.emit_event = emit_event
    ap.event_loop = asyncio.get_running_loop()
    ap.instance_config = SimpleNamespace(data={})
    ap.task_mgr = AsyncTaskManager(ap)
    h, binding = secured_host(ap, workspace_id='workspace-test', plugin_identity='langbot-team/LocalAgent')
    from sqlalchemy.ext.asyncio import AsyncSession
    from langbot.pkg.api.application.api import ApplicationAPI

    setting = ap.persistence_mgr.execute_async.return_value.first.return_value[0]
    setting.permission_declaration = {'workspace_operations': ['pipeline.list'], 'capabilities': []}
    setting.permission_grants = {'workspace_operations': ['pipeline.list'], 'capabilities': []}
    async with AsyncSession(clean_agent_state, expire_on_commit=False) as session:
        session.add(setting)
        await session.commit()

    async def execute_async(statement):
        async with AsyncSession(clean_agent_state) as session:
            return await session.execute(statement)

    ap.persistence_mgr.execute_async = execute_async
    ap.application_api = ApplicationAPI(ap)
    connector.require_workspace_context = AsyncMock()
    connector._setting_for_plugin = AsyncMock(return_value=(None, setting))
    connector._binding_from_setting = lambda context, setting: binding
    connector._runtime_handler = lambda: h

    class Bridge:
        async def call_action(self, action, data, timeout=15, **kwargs):
            token = h._current_action_context.set(binding)
            try:
                response = await h.actions[action.value](data)
            finally:
                h._current_action_context.reset(token)
            assert response.code == 0, response.message
            return response.data

    ctx = RunnerContext.model_validate(source_context)
    ctx.runtime.deadline_at = time.time() - 1
    api = RunnerAPIProxy(ctx, Bridge())
    connector.results = [
        {'type': 'message.completed', 'data': {'message': {'role': 'assistant', 'content': 'recovered'}}},
        {'type': 'run.completed', 'data': {'finish_reason': 'stop'}},
    ]
    connector.delay = 0.2
    run_runner = connector.run_runner

    async def reply_then_run(plugin_author, plugin_name, runner_name, context):
        recovered_api = RunnerAPIProxy(RunnerContext.model_validate(context), Bridge())
        active_bot = ap.platform_mgr.get_bot_by_uuid.return_value
        ap.platform_mgr.get_bot_by_uuid.return_value = SimpleNamespace(adapter=object())
        try:
            with pytest.raises(AssertionError, match='no longer active'):
                async with recovered_api.reply_stream() as reply:
                    await reply.update('must not be delivered')
        finally:
            ap.platform_mgr.get_bot_by_uuid.return_value = active_bot
        assert transport.await_count == 0
        async with recovered_api.reply_stream() as reply:
            await reply.update('explicit recovery reply')
        await recovered_api.call_tool('event_reply', {'text': 'recovered tool reply'})
        async for result in run_runner(plugin_author, plugin_name, runner_name, context):
            yield result

    connector.run_runner = reply_then_run
    if resume:
        child = await api.run_resume(from_sequence=3)
        repeated = await api.run_resume(from_sequence=3)
    else:
        child = await api.run_retry()
        repeated = await api.run_retry()
    assert child.run_id != source_id
    assert repeated.run_id == child.run_id
    assert len(ap.task_mgr.tasks) == 1
    await asyncio.wait_for(ap.task_mgr.tasks[0].task, 3)
    store = RunLedgerStore(clean_agent_state)
    assert (await store.get_run(source_id))['status'] == 'failed'
    recovered = await store.get_run(child.run_id)
    assert recovered['status'] == 'completed'
    assert recovered['deadline_at'] > time.time()
    request = connector.contexts[-1]['runtime']['metadata']['recovery']
    assert request['source_run_id'] == source_id
    assert request['mode'] == ('resume' if resume else 'retry')
    assert len(request['events']) == (3 if resume else 0)
    assert connector.contexts[-1]['input']['text'] == source_context['input']['text']
    assert ap.pipeline_service.get_pipeline.call_args.args[1] == 'pipeline_001'
    assert transport.await_count == 3
    explicit = transport.call_args_list[0].kwargs
    assert explicit.get('text', explicit.get('content')) == 'explicit recovery reply'
    tool_reply = transport.call_args_list[1].kwargs
    assert tool_reply.get('text', tool_reply.get('content')) == 'recovered tool reply'
    sent = transport.call_args_list[2].kwargs
    text = sent['text'] if platform == 'telegram' else sent['content']
    assert 'wrapped:MASKED' in text and 'recovered' not in text
    if platform == 'telegram':
        assert sent['chat_id'] == -100 and sent['message_thread_id'] == 77
        assert sent.get('reply_to_message_id') == (10 if quote_origin else None)
    else:
        if quote_origin:
            assert sent['reference'].message_id == 10 and sent['reference'].channel_id == 789
        else:
            assert sent.get('reference') is None
        assert '<@456>' in text
    resources = connector.contexts[-1]['resources']
    assert [operation['id'] for operation in resources['workspace_operations']] == ['pipeline.list']
    assert 'platform_send_message' in {tool['tool_name'] for tool in resources['tools']}
    assert ap.pipeline_mgr.pipelines == [], 'Recovery must not replace the published Pipeline runtime'
    events, *_ = await store.page_run_events(run_id=source_id)
    assert [e['type'] for e in events] == ['tool.call.started', 'tool.call.completed', 'run.failed']


@pytest.mark.asyncio
async def test_resume_keeps_ancestor_checkpoints_and_rejects_stale_cursor(clean_agent_state):
    from langbot.pkg.agent.runner.run_recovery import _resume_events

    store = RunLedgerStore(clean_agent_state)
    inherited = [
        {'type': 'tool.call.started', 'data': {'tool_call_id': 'committed'}},
        {'type': 'tool.call.completed', 'data': {'tool_call_id': 'committed', 'result': {'ok': True}}},
    ]
    await store.create_run(
        run_id='second',
        event_id='event',
        binding_id='binding',
        runner_id='runner',
        authorization={'recovery_checkpoint': inherited},
    )
    await store.append_event(run_id='second', sequence=1, event_type='run.failed', data={'error': 'disconnect'})
    events, sequence = await _resume_events(store, 'second', 1)
    assert sequence == 1
    assert events[:2] == inherited
    with pytest.raises(ValueError, match='latest committed'):
        await _resume_events(store, 'second', 0)


@pytest.mark.asyncio
async def test_resume_refuses_tool_with_unknown_effects(clean_agent_state):
    from langbot.pkg.agent.runner.run_recovery import _resume_events

    store = RunLedgerStore(clean_agent_state)
    await store.create_run(run_id='unfinished', event_id='event', binding_id='binding', runner_id='runner')
    await store.append_event(
        run_id='unfinished', sequence=1, event_type='tool.call.started', data={'tool_call_id': 'unknown'}
    )
    with pytest.raises(ValueError, match='no committed completion'):
        await _resume_events(store, 'unfinished', 1)
