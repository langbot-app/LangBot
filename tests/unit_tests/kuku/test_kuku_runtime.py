from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.kuku.runtime import (
    KukuRuntime,
    _parse_hhmm,
    _unwrap_invoke_llm_result,
    in_quiet_hours,
)


def test_in_quiet_hours_empty_config():
    assert in_quiet_hours({}) is False


def test_in_quiet_hours_missing_end():
    assert in_quiet_hours({'start': '09:00', 'timezone': 'UTC'}) is False


def test_parse_hhmm_valid_and_invalid():
    t = _parse_hhmm('09:30')
    assert t is not None
    assert t.hour == 9 and t.minute == 30
    assert _parse_hhmm('invalid') is None
    assert _parse_hhmm('25:00') is None


def test_unwrap_invoke_llm_tuple_vs_message():
    assert _unwrap_invoke_llm_result(('only', 'extra')) == 'only'
    assert _unwrap_invoke_llm_result('plain') == 'plain'


def _build_group_event(
    *,
    channel_id: str = 'channel-1',
    components: list[platform_message.MessageComponent],
    source_platform_object=None,
) -> platform_events.GroupMessage:
    return platform_events.GroupMessage(
        sender=platform_entities.GroupMember(
            id='user-1',
            member_name='User 1',
            permission=platform_entities.Permission.Member,
            group=platform_entities.Group(
                id=channel_id,
                name='general',
                permission=platform_entities.Permission.Member,
            ),
        ),
        message_chain=platform_message.MessageChain(components),
        source_platform_object=source_platform_object,
    )


@pytest.mark.asyncio
async def test_kuku_runtime_replies_immediately_when_discord_message_mentions_bot():
    runtime_bot = SimpleNamespace(
        enable=True,
        bot_entity=SimpleNamespace(adapter='discord'),
        adapter=SimpleNamespace(
            bot_account_id='bot-123',
            reply_message=AsyncMock(),
        ),
    )
    app = SimpleNamespace(
        kuku_service=SimpleNamespace(
            get_group_settings=AsyncMock(
                return_value={
                    'bot_uuid': 'bot-1',
                    'platform': 'discord',
                    'group_id': 'channel-1',
                    'persona_id': 'kuku-sunny',
                    'enabled': True,
                }
            ),
            get_persona=AsyncMock(
                return_value={
                    'id': 'kuku-sunny',
                    'system_prompt': 'You are KUKU.',
                }
            ),
        ),
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=runtime_bot)),
    )
    runtime = KukuRuntime(app)
    runtime._generate_reactive_reply = AsyncMock(return_value='hello from kuku')

    event = _build_group_event(
        components=[
            platform_message.At(target='bot-123'),
            platform_message.Plain(text='how are you?'),
        ]
    )

    handled = await runtime.maybe_handle_discord_group_message('bot-1', event)

    assert handled is True
    runtime._generate_reactive_reply.assert_awaited_once()
    assert runtime._generate_reactive_reply.call_args[0][1] is runtime_bot
    runtime_bot.adapter.reply_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_kuku_runtime_replies_immediately_when_message_replies_to_bot():
    runtime_bot = SimpleNamespace(
        enable=True,
        bot_entity=SimpleNamespace(adapter='discord'),
        adapter=SimpleNamespace(
            bot_account_id='bot-123',
            reply_message=AsyncMock(),
        ),
    )
    app = SimpleNamespace(
        kuku_service=SimpleNamespace(
            get_group_settings=AsyncMock(
                return_value={
                    'bot_uuid': 'bot-1',
                    'platform': 'discord',
                    'group_id': 'channel-1',
                    'persona_id': 'kuku-sunny',
                    'enabled': True,
                }
            ),
            get_persona=AsyncMock(
                return_value={
                    'id': 'kuku-sunny',
                    'system_prompt': 'You are KUKU.',
                }
            ),
        ),
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=runtime_bot)),
    )
    runtime = KukuRuntime(app)
    runtime._generate_reactive_reply = AsyncMock(return_value='reply from kuku')

    discord_source = SimpleNamespace(
        reference=SimpleNamespace(
            resolved=SimpleNamespace(
                author=SimpleNamespace(id='bot-123'),
                content='previous kuku message',
            )
        )
    )
    event = _build_group_event(
        components=[platform_message.Plain(text='tell me more')],
        source_platform_object=discord_source,
    )

    handled = await runtime.maybe_handle_discord_group_message('bot-1', event)

    assert handled is True
    runtime._generate_reactive_reply.assert_awaited_once()
    assert runtime._generate_reactive_reply.call_args[0][1] is runtime_bot
    runtime_bot.adapter.reply_message.assert_awaited_once()
