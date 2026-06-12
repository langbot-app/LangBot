from __future__ import annotations

import pathlib
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from langbot.pkg.platform.adapters.discord.adapter import DiscordAdapter
import langbot.pkg.platform.adapters.discord.adapter as discord_adapter_module
from langbot.pkg.platform.adapters.discord.event_converter import DiscordEventConverter
from langbot.pkg.platform.adapters.discord.message_converter import DiscordMessageConverter
from langbot.pkg.platform.adapters.discord.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


def make_adapter() -> DiscordAdapter:
    return DiscordAdapter({'client_id': '123', 'token': 'fake'}, DummyLogger())


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'discord'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def test_discord_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_discord_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_discord_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_discord_adapter_dispatches_most_specific_eba_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def wildcard_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    async def message_listener(event, adapter):
        calls.append('message')

    adapter.register_listener(platform_events.Event, wildcard_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)
    adapter.register_listener(
        platform_events.MessageReceivedEvent,
        message_listener,
    )

    event = platform_events.MessageReceivedEvent(
        message_id=1,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        sender={'id': 1},
        chat_id=1,
    )

    await adapter._dispatch_eba_event(event)

    assert calls == ['message']


@pytest.mark.asyncio
async def test_discord_message_converter_maps_mentions_and_text_to_target():
    content, files = await DiscordMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi '),
                platform_message.At(target='123'),
                platform_message.Plain(text=' all '),
                platform_message.AtAll(),
            ]
        )
    )

    assert content == 'hi <@123> all @everyone'
    assert files == []


def test_discord_message_converter_splits_discord_mentions():
    components = DiscordMessageConverter._text_components('hi <@123> and @everyone')

    assert isinstance(components[0], platform_message.Plain)
    assert components[0].text == 'hi '
    assert isinstance(components[1], platform_message.At)
    assert components[1].target == '123'
    assert isinstance(components[3], platform_message.AtAll)


def fake_user(user_id=123, name='user', bot=False):
    return SimpleNamespace(
        id=user_id,
        name=name,
        display_name=name.title(),
        bot=bot,
        display_avatar=SimpleNamespace(url=f'https://cdn.example/{user_id}.png'),
    )


def fake_guild(guild_id=456):
    return SimpleNamespace(
        id=guild_id,
        name='Guild',
        member_count=3,
        icon=None,
        owner_id=1,
    )


def fake_channel(channel_id=789, guild=None):
    return SimpleNamespace(
        id=channel_id,
        name='general',
        guild=guild,
    )


def fake_message(content='hello <@123>', *, guild=None, channel=None, author=None, message_id=999):
    guild = guild if guild is not None else fake_guild()
    channel = channel if channel is not None else fake_channel(guild=guild)
    author = author if author is not None else fake_user()
    return SimpleNamespace(
        id=message_id,
        content=content,
        author=author,
        channel=channel,
        guild=guild,
        attachments=[],
        created_at=datetime.datetime(2026, 5, 7, tzinfo=datetime.UTC),
        edited_at=datetime.datetime(2026, 5, 7, 0, 1, tzinfo=datetime.UTC),
    )


@pytest.mark.asyncio
async def test_discord_converter_maps_message_edit_delete_and_reaction_events():
    message = fake_message()
    received = await DiscordEventConverter.message_to_eba(message)

    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert received.type == 'message.received'
    assert received.adapter_name == 'discord'
    assert received.chat_type == platform_entities.ChatType.GROUP
    assert received.chat_id == 789
    assert received.group.id == 456
    assert isinstance(received.message_chain[1], platform_message.Plain)
    assert isinstance(received.message_chain[2], platform_message.At)

    edited = await DiscordEventConverter.message_edit_to_eba(message, fake_message(content='edited', message_id=999))
    assert isinstance(edited, platform_events.MessageEditedEvent)
    assert edited.type == 'message.edited'
    assert str(edited.new_content) == 'edited'

    deleted = await DiscordEventConverter.message_delete_to_eba(message)
    assert isinstance(deleted, platform_events.MessageDeletedEvent)
    assert deleted.type == 'message.deleted'
    assert deleted.message_id == 999

    reaction = SimpleNamespace(message=message, emoji='👍')
    reaction_event = DiscordEventConverter.reaction_to_eba(reaction, fake_user(321, 'reactor'), True)
    assert isinstance(reaction_event, platform_events.MessageReactionEvent)
    assert reaction_event.type == 'message.reaction'
    assert reaction_event.reaction == '👍'
    assert reaction_event.user.id == 321


@pytest.mark.asyncio
async def test_discord_converter_maps_uncached_raw_gateway_events():
    raw_delete = SimpleNamespace(message_id=10, channel_id=20, guild_id=30)
    deleted = await DiscordEventConverter.target2yiri(('raw_message_delete', raw_delete), bot_user_id=1)
    assert isinstance(deleted, platform_events.MessageDeletedEvent)
    assert deleted.message_id == 10
    assert deleted.chat_id == 20
    assert deleted.group.id == 30

    raw_reaction = SimpleNamespace(
        message_id=11,
        channel_id=21,
        guild_id=31,
        user_id=41,
        emoji='🔥',
        member=fake_user(41, 'member'),
    )
    reaction = await DiscordEventConverter.target2yiri(('raw_reaction_add', raw_reaction), bot_user_id=1)
    assert isinstance(reaction, platform_events.MessageReactionEvent)
    assert reaction.reaction == '🔥'
    assert reaction.is_add is True
    assert reaction.user.id == 41


def test_discord_converter_maps_member_and_bot_guild_events():
    guild = fake_guild()
    member = SimpleNamespace(
        **fake_user(123, 'member').__dict__,
        guild=guild,
        joined_at=datetime.datetime(2026, 5, 7, tzinfo=datetime.UTC),
    )

    joined = DiscordEventConverter.member_join_to_eba(member, bot_user_id=999)
    assert isinstance(joined, platform_events.MemberJoinedEvent)
    assert joined.join_type == 'direct'

    bot_joined = DiscordEventConverter.member_join_to_eba(member, bot_user_id=123)
    assert isinstance(bot_joined, platform_events.BotInvitedToGroupEvent)

    bot_invited = DiscordEventConverter.guild_join_to_eba(guild)
    bot_removed = DiscordEventConverter.guild_remove_to_eba(guild)
    assert isinstance(bot_invited, platform_events.BotInvitedToGroupEvent)
    assert isinstance(bot_removed, platform_events.BotRemovedFromGroupEvent)


@pytest.mark.asyncio
async def test_discord_send_and_reply_omit_empty_files_and_return_message_result(monkeypatch):
    adapter = make_adapter()
    sent = SimpleNamespace(id=111)
    channel = SimpleNamespace(send=AsyncMock(return_value=sent))
    object.__setattr__(adapter, '_get_channel', AsyncMock(return_value=channel))

    result = await adapter.send_message(
        'group',
        '789',
        platform_message.MessageChain([platform_message.Plain(text='hello')]),
    )

    assert result.message_id == 111
    assert channel.send.await_args.kwargs == {'content': 'hello'}

    monkeypatch.setattr(discord_adapter_module.discord, 'Message', SimpleNamespace)
    source_message = SimpleNamespace(channel=channel)
    source = platform_events.MessageReceivedEvent(
        message_id=1,
        source_platform_object=source_message,
    )
    result = await adapter.reply_message(
        source,
        platform_message.MessageChain([platform_message.Plain(text='reply')]),
        quote_origin=True,
    )

    assert result.message_id == 111
    assert channel.send.await_args.kwargs['content'] == 'reply'
    assert channel.send.await_args.kwargs['reference'] is source_message
    assert channel.send.await_args.kwargs['mention_author'] is False
