"""RuntimeBot ingress tracing: one inbound event owns one v2 execution chain."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import asyncio

import pytest

from langbot.pkg.api.http.context import ExecutionContext

TEST_CONTEXT = ExecutionContext(
    instance_uuid='instance-test',
    workspace_uuid='workspace-test',
    placement_generation=1,
    bot_uuid='bot-1',
)


class FakeTelemetryManager:
    def __init__(self, config=None):
        self.telemetry_config = (
            {'url': 'https://space.example.test', 'execution_trace': 'all'} if config is None else config
        )
        self.sent: list[dict] = []

    async def send(self, payload: dict) -> bool:
        self.sent.append(payload)
        return True


def make_bot(event_bindings: list[dict], config=None, agent=None):
    from langbot.pkg.platform.botmgr import RuntimeBot
    from langbot.pkg.telemetry.execution import ExecutionCounters

    manager = FakeTelemetryManager(config)
    counters = ExecutionCounters(manager)
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(
        uuid='bot-1',
        workspace_uuid=TEST_CONTEXT.workspace_uuid,
        event_bindings=event_bindings,
        plugin_processors=[],
    )
    bot.execution_context = TEST_CONTEXT
    bot.workspace_uuid = TEST_CONTEXT.workspace_uuid
    bot.placement_generation = TEST_CONTEXT.placement_generation
    bot.logger = SimpleNamespace(info=AsyncMock(), warning=AsyncMock(), error=AsyncMock(), debug=AsyncMock())
    bot.adapter = FakeAdapter()
    bot.ap = SimpleNamespace(
        telemetry=SimpleNamespace(execution=counters),
        agent_service=SimpleNamespace(get_agent=AsyncMock(return_value=agent)),
        pipeline_service=SimpleNamespace(get_pipeline=AsyncMock(return_value=None)),
    )
    return bot, manager, counters


def message_received_event():
    from langbot_plugin.api.entities.builtin.platform import entities, events, message

    return events.MessageReceivedEvent(
        message_id='message-1',
        message_chain=message.MessageChain([message.Plain(text='hello')]),
        sender=entities.User(id='user-1', nickname='QA User'),
        chat_type=entities.ChatType.PRIVATE,
        chat_id='user-1',
    )


class FakeAdapter:
    async def get_supported_apis(self):
        return []


async def flushed_records(counters, manager) -> list[dict]:
    """Flush buffered telemetry and return everything the event emitted.

    Records are batched and uploaded by ``ExecutionCounters.flush()``; there is
    no per-trace direct send any more.
    """

    await counters.flush()
    assert manager.sent, 'expected the flushed telemetry batch'
    return [record for payload in manager.sent for record in payload.get('records', [])]


def execution_nodes(records: list[dict]) -> list[dict]:
    return [record for record in records if record.get('event_type') == 'execution_node']


def execution_chains(records: list[dict]) -> list[dict]:
    return [record for record in records if record.get('event_type') == 'execution_chain']


@pytest.mark.asyncio
async def test_route_miss_emits_nothing():
    bot, manager, counters = make_bot([])

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    await counters.flush()
    await counters.shutdown()
    assert manager.sent == []
    assert counters.records == []
    assert counters.dropped == 0
    assert counters.registry == {}


@pytest.mark.asyncio
async def test_unavailable_route_target_carries_route_identity():
    bot, manager, counters = make_bot(
        [
            {
                'id': 'agent-binding',
                'enabled': True,
                'event_pattern': 'message.received',
                'target_type': 'agent',
                'target_uuid': 'agent-1',
            }
        ]
    )

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    nodes = execution_nodes(await flushed_records(counters, manager))
    assert [(node['family'], node['outcome'], node['mode']) for node in nodes] == [
        ('event_route', 'failed', 'agent'),
        ('platform_event', 'success', 'none'),
    ]
    assert nodes[0]['route_ref'] == 'agent:agent-1'
    assert nodes[1]['route_ref'] == ''


@pytest.mark.asyncio
async def test_discarded_route_is_only_logged_locally():
    bot, manager, counters = make_bot(
        [
            {
                'id': 'discard-binding',
                'enabled': True,
                'event_pattern': '*',
                'target_type': 'discard',
            }
        ]
    )

    await bot._handle_platform_event(SimpleNamespace(type='platform.member.joined'), FakeAdapter())

    await counters.flush()
    assert manager.sent == []
    assert counters.records == []
    assert bot.logger.info.await_args.kwargs['metadata']['status'] == 'discarded'


@pytest.mark.asyncio
async def test_telemetry_opt_out_emits_nothing():
    bot, manager, counters = make_bot([], config={'url': 'https://space.example.test', 'disable_telemetry': True})

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    assert manager.sent == []
    assert counters.records == []
    assert counters.registry == {}


@pytest.mark.asyncio
async def test_route_trace_scope_is_restored_after_dispatch():
    from langbot.pkg.telemetry import trace as trace_mod

    bot, _, counters = make_bot([])
    assert trace_mod.current() is None

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    assert trace_mod.current() is None
    buffered = list(counters.records)
    # A later record outside the ingress must not join the closed chain, and an
    # observation without an owning chain is not buffered at all.
    from langbot.pkg.telemetry.execution import record

    record(bot.ap, TEST_CONTEXT, family='platform_api', operation='send_message', outcome='success')
    assert counters.records == buffered
    assert counters.registry == {}


@pytest.mark.asyncio
async def test_mock_adapter_route_miss_is_not_reported():
    """Mock adapter objects used by other tests must not break the ingress path."""
    bot, manager, counters = make_bot([])
    adapter = Mock()

    await bot._handle_platform_event(message_received_event(), adapter)

    await counters.flush()
    assert manager.sent == []


def business_route(**overrides):
    return {
        'id': 'route',
        'enabled': True,
        'event_pattern': '*',
        'target_type': 'agent',
        'target_uuid': 'agent-1',
        **overrides,
    }


async def assert_no_upload(counters, manager):
    assert counters.records == []
    assert counters.task is None
    await counters.flush()
    await counters.shutdown()
    assert manager.sent == []
    assert counters.health() == {
        'records_buffered': 0,
        'records_sent': 0,
        'records_dropped': 0,
        'executions_in_flight': 0,
    }


@pytest.mark.parametrize('edition', ['community', 'cloud'])
@pytest.mark.parametrize('mode', ['all', 'sampled', 'failures', 'off'])
@pytest.mark.parametrize(
    'routes',
    [
        [],
        [business_route(enabled=False)],
        [business_route(event_pattern='group.member_joined')],
        [business_route(filters=[{'field': 'chat_id', 'operator': 'eq', 'value': 'another-chat'}])],
        [business_route(target_type='discard', priority=10), business_route(priority=1)],
    ],
)
async def test_unrouted_events_never_upload_in_any_mode(monkeypatch, edition, mode, routes):
    from langbot.pkg.utils import constants

    monkeypatch.setattr(constants, 'edition', edition)
    bot, manager, counters = make_bot(routes, config={'url': 'https://space.example.test', 'execution_trace': mode})
    bot._dispatch_eba_message_to_pipeline = AsyncMock()
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    await assert_no_upload(counters, manager)
    # Normal local route diagnostics still exist, including explicit discard.
    assert bot.logger.info.await_args.kwargs['metadata']['status'] in {'not_matched', 'discarded'}


@pytest.mark.parametrize('mode', ['all', 'sampled', 'failures'])
async def test_matched_target_failure_is_retained_even_after_root_success(mode):
    bot, manager, counters = make_bot(
        [business_route()],
        config={
            'url': 'https://space.example.test',
            'execution_trace': mode,
            'execution_trace_sample': 100000,
        },
    )
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    records = await flushed_records(counters, manager)
    (chain,) = execution_chains(records)
    assert chain['outcome'] == 'failed'
    assert chain['error'] == 'processor_not_found'
    if mode == 'failures':
        assert execution_nodes(records) == []
    await counters.shutdown()


def install_processor(bot, patterns=None):
    bot.bot_entity.plugin_processors = [{'processor_uuid': 'processor', 'enabled': True}]
    bot.ap.agent_service.get_agent = AsyncMock(
        return_value={
            'kind': 'event_processor',
            'component_ref': 'plugin:test/runner/default',
        }
    )
    bot.ap.runner_registry = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                usages=['event'],
                supported_event_patterns=['*'] if patterns is None else patterns,
            )
        )
    )
    bot._agent_product_to_binding = Mock(return_value=SimpleNamespace())
    bot._eba_event_to_agent_envelope = Mock(return_value=SimpleNamespace())

    async def run(*args, **kwargs):
        from langbot.pkg.telemetry.execution import record

        record(bot.ap, TEST_CONTEXT, family='runner', operation='execute', outcome='success')
        if False:
            yield None

    bot.ap.agent_run_orchestrator = SimpleNamespace(run=run)


@pytest.mark.parametrize('primary', ['miss', 'discard'])
@pytest.mark.parametrize('primary_first', [True, False])
async def test_matching_subscription_admits_chain_regardless_of_primary_order(primary, primary_first):
    from langbot.pkg.telemetry.execution import record

    routes = [] if primary == 'miss' else [business_route(target_type='discard')]
    bot, manager, counters = make_bot(routes)
    install_processor(bot)
    bot.bot_entity.plugin_processors *= 2  # Duplicate subscriptions still execute once.
    original = bot._dispatch_eba_event_to_processor
    first_done = asyncio.Event()
    run_calls = []

    async def ordered_dispatch(event, adapter, event_binding=None, agent=None, execution_id=None):
        is_primary = event_binding is None
        if is_primary != primary_first:
            await first_done.wait()
        result = await original(event, adapter, event_binding, agent, execution_id)
        if not is_primary:
            run_calls.append(result)
        if is_primary == primary_first:
            first_done.set()
        return result

    async def discard_side_effect(*args, **kwargs):
        # A discarded message can still trigger a webhook/adapter side effect.
        # A concurrent admitted subscriber must not expose this branch's node.
        record(bot.ap, TEST_CONTEXT, family='platform_api', operation='discard_side_effect', outcome='success')
        await counters.flush()

    bot._dispatch_eba_event_to_processor = ordered_dispatch
    bot._dispatch_eba_message_to_pipeline = discard_side_effect
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    records = await flushed_records(counters, manager)
    (chain,) = execution_chains(records)
    nodes = execution_nodes(records)
    assert len(run_calls) == 1
    assert chain['stage_count'] == 3
    assert {node['family'] for node in nodes} == {'runner', 'event_route', 'platform_event'}
    assert all(node['outcome'] == 'success' for node in nodes)
    (root,) = [node for node in nodes if node['root']]
    assert root['family'] == 'platform_event'
    assert all(node['parent_node_id'] == root['node_id'] for node in nodes if not node['root'])
    assert all(node['event_id'] == chain['event_id'] for node in nodes)
    await counters.shutdown()


@pytest.mark.parametrize('kind', ['disabled', 'pattern_miss', 'no_patterns', 'missing', 'declaration_error'])
async def test_unmatched_subscription_cannot_admit_event(kind):
    bot, manager, counters = make_bot([])
    install_processor(bot)
    if kind == 'disabled':
        bot.bot_entity.plugin_processors[0]['enabled'] = False
    elif kind in {'pattern_miss', 'no_patterns'}:
        install_processor(bot, [] if kind == 'no_patterns' else ['group.member_joined'])
    elif kind == 'missing':
        bot.ap.agent_service.get_agent.return_value = None
    else:
        bot.ap.runner_registry.get.side_effect = RuntimeError('unavailable')
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    await assert_no_upload(counters, manager)


@pytest.mark.parametrize('failure', [RuntimeError('runner failed'), TimeoutError('timeout'), asyncio.CancelledError()])
async def test_matched_subscription_keeps_failed_timeout_and_cancelled_execution(failure):
    bot, manager, counters = make_bot([], config={'url': 'https://space.example.test', 'execution_trace': 'failures'})
    install_processor(bot)

    async def run(*args, **kwargs):
        raise failure
        yield

    bot.ap.agent_run_orchestrator.run = run
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    (chain,) = execution_chains(await flushed_records(counters, manager))
    assert chain['outcome'] == 'failed'
    assert chain['error']
    await counters.shutdown()


@pytest.mark.parametrize('processor', ['agent', 'pipeline', 'invalid', 'expired', 'duplicate'])
async def test_interaction_admission_requires_valid_callback(processor):
    from langbot_plugin.api.entities.builtin.platform import events

    bot, manager, counters = make_bot([])
    callbacks = SimpleNamespace(
        consume_callback=AsyncMock(return_value={'processor_type': processor, 'processor_id': 'target'}),
        acknowledge_submission=AsyncMock(),
    )
    if processor in {'expired', 'duplicate'}:
        callbacks.consume_callback.side_effect = ValueError(processor)
    bot.ap.agent_run_orchestrator = SimpleNamespace(interaction_manager=callbacks)
    bot._resume_agent_interaction = AsyncMock(side_effect=ValueError('target unavailable'))
    event = events.PlatformSpecificEvent(platform='test', action='interaction.submitted', data={})
    await bot._handle_platform_event(event, FakeAdapter())
    if processor in {'agent', 'pipeline'}:
        (chain,) = execution_chains(await flushed_records(counters, manager))
        assert chain['outcome'] == 'failed'
        callbacks.acknowledge_submission.assert_awaited_once()
        await counters.shutdown()
    else:
        callbacks.acknowledge_submission.assert_not_awaited()
        await assert_no_upload(counters, manager)


async def test_rejected_event_does_not_contaminate_next_matched_event_or_monitoring():
    from langbot.pkg.telemetry import trace

    bot, manager, counters = make_bot([])
    bot._persist_monitoring_ingress = AsyncMock()
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    assert bot._persist_monitoring_ingress.await_count == 2
    assert counters.records == []
    assert trace.current() is None
    assert trace.node_stack() == ()
    assert counters.registry == {}
    bot.bot_entity.event_bindings = [business_route()]
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    assert len(execution_chains(await flushed_records(counters, manager))) == 1
    await counters.shutdown()


async def test_pending_gate_blocks_nested_and_rpc_records_and_failure_fallback():
    import contextvars
    from langbot.pkg.telemetry import execution, trace

    bot, manager, counters = make_bot([])
    with pytest.raises(RuntimeError):
        with execution.ingress(bot.ap, context=TEST_CONTEXT, execution_id='pending', require_route=True, debug=True):
            with execution.ingress(bot.ap, context=TEST_CONTEXT, debug=True):
                execution.bind_trace(bot.ap, 'run-alias')
                execution.record(bot.ap, TEST_CONTEXT, family='tool', operation='nested', outcome='failed')

                async def rpc():
                    execution.record(
                        bot.ap,
                        TEST_CONTEXT,
                        execution_id='run-alias',
                        family='platform_api',
                        operation='rpc',
                        outcome='failed',
                    )
                    await counters.flush()

                await contextvars.Context().run(asyncio.create_task, rpc())
            assert counters.records == []
            raise RuntimeError('failed before a route matched')
    assert trace.current() is None
    await assert_no_upload(counters, manager)


@pytest.mark.parametrize('origin', ['api', 'webui'])
async def test_independent_debug_entry_still_reports(origin):
    from langbot.pkg.telemetry import execution

    bot, manager, counters = make_bot([], config={'url': 'https://space.example.test', 'execution_trace': 'failures'})
    with execution.ingress(
        bot.ap,
        context=TEST_CONTEXT,
        execution_id='debug',
        debug=True,
        origin=origin,
        synthetic_event='message.received',
    ):
        execution.record(bot.ap, TEST_CONTEXT, family='runner', operation='execute', outcome='success')
    (chain,) = execution_chains(await flushed_records(counters, manager))
    assert chain['debug'] is True
    assert chain['origin'] == origin
    await counters.shutdown()


@pytest.mark.parametrize('edition', ['community', 'cloud'])
async def test_admission_does_not_override_telemetry_opt_out(monkeypatch, edition):
    from langbot.pkg.utils import constants

    monkeypatch.setattr(constants, 'edition', edition)
    bot, manager, counters = make_bot(
        [business_route()],
        config={
            'url': 'https://space.example.test',
            'disable_telemetry': True,
        },
    )
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    await assert_no_upload(counters, manager)


async def test_unrelated_broken_subscription_does_not_poison_matched_delivery():
    bot, manager, counters = make_bot([business_route(target_type='pipeline')])
    bot._dispatch_eba_message_to_pipeline = AsyncMock()
    bot.bot_entity.plugin_processors = [{'processor_uuid': 'missing'}]
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    records = await flushed_records(counters, manager)
    (chain,) = execution_chains(records)
    assert chain['outcome'] == 'success'
    assert chain['error'] == ''
    assert all(node['outcome'] == 'success' for node in execution_nodes(records))
    bot.logger.error.assert_awaited_once()
    await counters.shutdown()


async def test_pending_event_cancelled_during_dispatch_never_uploads():
    bot, manager, counters = make_bot([])
    started = asyncio.Event()

    async def waiting_dispatch(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    bot._dispatch_eba_event_to_processor = waiting_dispatch
    task = asyncio.create_task(bot._handle_platform_event(message_received_event(), FakeAdapter()))
    await started.wait()
    await counters.flush()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await assert_no_upload(counters, manager)


async def test_retry_of_matched_batch_cannot_include_intervening_unrouted_event():
    bot, manager, counters = make_bot([business_route()])
    await bot._handle_platform_event(message_received_event(), FakeAdapter())
    expected = list(counters.records)
    original_send = manager.send
    manager.send = AsyncMock(return_value=False)
    assert await counters.flush() is False
    assert counters.records == expected
    bot.bot_entity.event_bindings = []
    ignored = message_received_event()
    ignored.message_id = 'ignored-message'
    await bot._handle_platform_event(ignored, FakeAdapter())
    assert counters.records == expected
    manager.send = original_send
    await counters.shutdown()
    sent = [record for batch in manager.sent for record in batch['records']]
    assert sent == expected
    assert counters.dropped == 0


async def test_valid_interaction_success_keeps_acknowledgement_and_execution():
    from langbot.pkg.telemetry.execution import record
    from langbot_plugin.api.entities.builtin.platform import events

    bot, manager, counters = make_bot([])

    async def acknowledge(*args):
        record(bot.ap, TEST_CONTEXT, family='platform_api', operation='ack', outcome='success')

    async def resume(*args):
        record(bot.ap, TEST_CONTEXT, family='runner', operation='execute', outcome='success')

    bot.ap.agent_run_orchestrator = SimpleNamespace(
        interaction_manager=SimpleNamespace(
            consume_callback=AsyncMock(return_value={'processor_type': 'agent'}),
            acknowledge_submission=acknowledge,
        )
    )
    bot._resume_agent_interaction = resume
    event = events.PlatformSpecificEvent(platform='test', action='interaction.submitted', data={})
    await bot._handle_platform_event(event, FakeAdapter())
    records = await flushed_records(counters, manager)
    (chain,) = execution_chains(records)
    assert chain['outcome'] == 'success'
    assert {node['family'] for node in execution_nodes(records)} == {'platform_event', 'platform_api', 'runner'}
    await counters.shutdown()
