"""RuntimeBot ingress tracing: one inbound event owns one execution trace."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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

    def start_send_task(self, payload: dict) -> None:
        self.sent.append(payload)


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
    """Flush buffered telemetry and return everything the pipeline emitted.

    Records are batched and uploaded by ``ExecutionCounters.flush()``; there is
    no per-trace direct send any more.
    """

    await counters.flush()
    assert manager.sent, 'expected the flushed telemetry batch'
    return [record for payload in manager.sent for record in payload.get('records', [])]


@pytest.mark.asyncio
async def test_route_miss_emits_one_closed_trace():
    bot, manager, counters = make_bot([])

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    records = await flushed_records(counters, manager)
    assert len(manager.sent) == 1
    trace_records = [item for item in records if item.get('event_type') == 'feature_execution']
    assert len(trace_records) == 1
    payload = trace_records[0]
    assert payload['event_type'] == 'feature_execution'
    # The execution identity is deterministic: one inbound event, one chain.
    assert payload['query_id'] == 'platform:bot-1:message-1'
    assert payload['instance_id'] == 'instance-test'
    assert payload['workspace_uuid'] == 'workspace-test'
    features = payload['features']
    assert features['schema'] == 1
    assert [(row['family'], row['operation'], row['outcome']) for row in features['observations']] == [
        ('event_route', 'message.received', 'skipped'),
        ('platform_event', 'message.received', 'success'),
    ]
    assert [row['seq'] for row in features['observations']] == [0, 1]
    assert all(row['trace_id'] == payload['query_id'] for row in features['observations'])
    assert all(row['adapter'] == 'FakeAdapter' for row in features['observations'])
    assert features['trace']['closed_by'] == 'event_done'
    # The trace is closed and deregistered: nothing dangles after the event.
    assert counters.traces == {}


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

    stages = (await flushed_records(counters, manager))[0]['features']['observations']
    assert [(stage['family'], stage['outcome'], stage['mode']) for stage in stages] == [
        ('event_route', 'failed', 'agent'),
        ('platform_event', 'success', 'none'),
    ]
    assert stages[0]['route_ref'] == 'agent:agent-1'
    assert stages[1]['route_ref'] == ''


@pytest.mark.asyncio
async def test_discarded_route_is_visible_without_user_values():
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

    stages = (await flushed_records(counters, manager))[0]['features']['observations']
    assert [stage['outcome'] for stage in stages] == ['skipped', 'success']
    assert stages[0]['operation'] == 'platform.member.joined'
    assert stages[0]['mode'] == 'none'


@pytest.mark.asyncio
async def test_telemetry_opt_out_emits_nothing():
    bot, manager, counters = make_bot([], config={'url': 'https://space.example.test', 'disable_telemetry': True})

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    assert manager.sent == []
    assert counters.records == []
    assert counters.traces == {}


@pytest.mark.asyncio
async def test_route_trace_scope_is_restored_after_dispatch():
    from langbot.pkg.telemetry import trace as trace_mod

    bot, _, counters = make_bot([])
    assert trace_mod.current() is None

    await bot._handle_platform_event(message_received_event(), FakeAdapter())

    assert trace_mod.current() is None
    buffered = list(counters.records)
    # A later record outside the ingress must not join the closed trace, and an
    # observation without an owning chain is not buffered at all.
    from langbot.pkg.telemetry.execution import record

    record(bot.ap, TEST_CONTEXT, family='platform_api', operation='send_message', outcome='success')
    assert counters.records == buffered
    assert counters.traces == {}


@pytest.mark.asyncio
async def test_adapter_call_without_ingress_still_counts():
    """Mock adapter objects used by other tests must not break the ingress path."""
    bot, manager, counters = make_bot([])
    adapter = Mock()

    await bot._handle_platform_event(message_received_event(), adapter)

    assert await flushed_records(counters, manager)
