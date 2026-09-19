"""Independent bot subscriptions must not change primary route delivery."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.platform.events import MemberJoinedEvent

from langbot.pkg.platform.botmgr import RuntimeBot


def make_bot(subscriptions):
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(uuid='bot', event_bindings=[], plugin_processors=subscriptions)
    bot.execution_context = 'workspace'
    bot._record_adapter_event = AsyncMock()
    bot._record_event_route_trace = AsyncMock()
    bot.logger = SimpleNamespace(error=AsyncMock())
    return bot


async def test_slow_failed_and_duplicate_subscriptions_do_not_block_primary_route():
    bot = make_bot(
        [
            {'processor_uuid': 'slow'},
            {'processor_uuid': 'failed'},
            {'processor_uuid': 'fast'},
            {'processor_uuid': 'fast'},
            {'processor_uuid': 'disabled', 'enabled': False},
        ]
    )
    started = []
    release = asyncio.Event()

    async def subscriber(event, adapter, uuid):
        started.append(uuid)
        if uuid == 'slow':
            await release.wait()
        if uuid == 'failed':
            raise ValueError('plugin error')

    async def primary(event, adapter):
        started.append('primary')

    bot._dispatch_plugin_subscription = subscriber
    bot._dispatch_eba_event_to_processor = primary
    task = asyncio.create_task(bot._handle_platform_event(MemberJoinedEvent(), None))
    for _ in range(10):
        await asyncio.sleep(0)
        if len(started) == 4:
            break
    assert set(started) == {'primary', 'slow', 'failed', 'fast'}
    assert started.count('fast') == 1
    assert not task.done()
    release.set()
    await task
    bot.logger.error.assert_awaited_once()


@pytest.mark.parametrize(
    'patterns,event_usage,expected',
    [
        (['group.member_joined'], True, 1),
        (['group.*'], True, 1),
        (['*'], True, 1),
        (['message.received'], True, 0),
        ([], True, 0),
        (['*'], False, 0),
    ],
)
async def test_matching_uses_live_runner_declaration(patterns, event_usage, expected):
    bot = make_bot([])
    bot.ap = SimpleNamespace(
        agent_service=SimpleNamespace(
            get_agent=AsyncMock(
                return_value={
                    'kind': 'event_processor',
                    'component_ref': 'plugin:test/runner/default',
                    'supported_event_patterns': ['stale.event'],
                }
            )
        ),
        runner_registry=SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(
                    usages=['event'] if event_usage else ['agent'],
                    supported_event_patterns=patterns,
                )
            )
        ),
    )
    bot._dispatch_eba_event_to_processor = AsyncMock()
    await bot._dispatch_plugin_subscription(MemberJoinedEvent(), None, 'processor')
    assert bot._dispatch_eba_event_to_processor.await_count == expected
    if expected:
        args = bot._dispatch_eba_event_to_processor.await_args.args
        assert args[2]['target_uuid'] == 'processor'
        assert args[3]['supported_event_patterns'] == patterns


async def test_missing_processor_is_logged_without_unscoped_lookup():
    bot = make_bot([])
    bot.ap = SimpleNamespace(agent_service=SimpleNamespace(get_agent=AsyncMock(return_value=None)))
    await bot._dispatch_plugin_subscription(MemberJoinedEvent(), None, 'missing')
    bot.ap.agent_service.get_agent.assert_awaited_once_with('workspace', 'missing')
    assert bot._record_event_route_trace.await_args.kwargs['status'] == 'failed'
