from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock

import pytest
import yaml

from langbot.pkg.platform.adapters.kook.adapter import KookAdapter
from langbot.pkg.platform.adapters.kook.event_converter import KookEventConverter
from langbot.pkg.platform.adapters.kook.message_converter import KookMessageConverter
from langbot.pkg.platform.adapters.kook.platform_api import PLATFORM_API_MAP, get_gateway
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


def make_adapter() -> KookAdapter:
    return KookAdapter({'token': 'fake', 'enable-stream-reply': False}, DummyLogger())


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'kook'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def fake_kook_message(**overrides):
    event = {
        'channel_type': 'GROUP',
        'type': 9,
        'author_id': 'u1',
        'target_id': 'c1',
        'msg_id': 'm1',
        'msg_timestamp': 1_775_000_000_000,
        'content': 'hi (met)u2(met) and (met)all(met)',
        'extra': {
            'channel_name': 'general',
            'guild_id': 'g1',
            'guild_name': 'Guild',
            'author': {
                'id': 'u1',
                'username': 'alice',
                'nickname': 'Alice',
                'avatar': 'https://example/avatar.png',
            },
            'mention': ['u2'],
            'mention_all': True,
        },
    }
    event.update(overrides)
    return event


def test_kook_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_kook_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_kook_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_kook_adapter_dispatches_most_specific_eba_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def event_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    async def message_listener(event, adapter):
        calls.append('message')

    adapter.register_listener(platform_events.Event, event_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)
    adapter.register_listener(platform_events.MessageReceivedEvent, message_listener)

    event = platform_events.MessageReceivedEvent(
        message_id='m1',
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        sender=platform_entities.User(id='u1'),
        chat_id='c1',
    )

    await adapter._dispatch_eba_event(event)

    assert calls == ['message']


@pytest.mark.asyncio
async def test_kook_message_converter_maps_target_text_mentions_and_source():
    chain = await KookMessageConverter.target2yiri(fake_kook_message(), bot_account_id='bot')

    assert isinstance(chain[0], platform_message.Source)
    assert chain[0].id == 'm1'
    assert isinstance(chain[1], platform_message.Plain)
    assert chain[1].text == 'hi '
    assert isinstance(chain[2], platform_message.At)
    assert chain[2].target == 'u2'
    assert isinstance(chain[4], platform_message.AtAll)


@pytest.mark.asyncio
async def test_kook_message_converter_maps_media_components():
    image = await KookMessageConverter.target2yiri(fake_kook_message(type=2, content='https://example/image.png'))
    assert isinstance(image[1], platform_message.Image)
    assert image[1].url == 'https://example/image.png'

    file_chain = await KookMessageConverter.target2yiri(
        fake_kook_message(type=4, content='https://example/file.bin', extra={'attachments': {'name': 'file.bin'}})
    )
    assert isinstance(file_chain[1], platform_message.File)
    assert file_chain[1].name == 'file.bin'

    voice = await KookMessageConverter.target2yiri(fake_kook_message(type=8, content='https://example/voice.mp3'))
    assert isinstance(voice[1], platform_message.Voice)


@pytest.mark.asyncio
async def test_kook_message_converter_maps_common_components_to_target():
    content, msg_type = await KookMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi '),
                platform_message.At(target='u1'),
                platform_message.Plain(text=' all '),
                platform_message.AtAll(),
            ]
        )
    )

    assert content == 'hi (met)u1(met) all (met)all(met)'
    assert msg_type == 1


@pytest.mark.asyncio
async def test_kook_event_converter_maps_group_private_and_platform_specific_events():
    group_event = await KookEventConverter.target2yiri(fake_kook_message(), bot_account_id='bot')
    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.type == 'message.received'
    assert group_event.adapter_name == 'kook'
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 'c1'
    assert group_event.group.id == 'c1'
    assert group_event.sender.id == 'u1'

    private_event = await KookEventConverter.target2yiri(
        fake_kook_message(channel_type='PERSON', target_id='u1', extra={'code': 'chat-code'}),
        bot_account_id='bot',
    )
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 'chat-code'
    assert private_event.group is None

    specific = await KookEventConverter.target2yiri({'type': 255, 'target_id': 'raw'}, bot_account_id='bot')
    assert isinstance(specific, platform_events.PlatformSpecificEvent)
    assert specific.action == '255'


@pytest.mark.asyncio
async def test_kook_event_converter_maps_legacy_events():
    legacy_group = await KookEventConverter.target2legacy(fake_kook_message(), bot_account_id='bot')
    assert isinstance(legacy_group, platform_events.GroupMessage)
    assert legacy_group.sender.group.id == 'c1'

    legacy_private = await KookEventConverter.target2legacy(
        fake_kook_message(channel_type='PERSON', target_id='u1'),
        bot_account_id='bot',
    )
    assert isinstance(legacy_private, platform_events.FriendMessage)


@pytest.mark.asyncio
async def test_kook_send_and_reply_pass_expected_payloads():
    adapter = make_adapter()
    adapter._request = AsyncMock(return_value={'code': 0, 'data': {'msg_id': 'sent'}})

    result = await adapter.send_message(
        'group',
        'c1',
        platform_message.MessageChain([platform_message.Plain(text='hello')]),
    )

    assert result.message_id == 'sent'
    adapter._request.assert_awaited_with(
        'POST',
        '/message/create',
        json={'target_id': 'c1', 'content': 'hello', 'type': 1},
    )

    source = await KookEventConverter.target2yiri(fake_kook_message(), bot_account_id='bot')
    await adapter.reply_message(source, platform_message.MessageChain([platform_message.Plain(text='reply')]), True)

    assert adapter._request.await_args_list[-1].args == ('POST', '/message/create')
    payload = adapter._request.await_args_list[-1].kwargs['json']
    assert payload['reply_msg_id'] == 'm1'
    assert payload['quote'] == 'm1'
    assert payload['content'] == 'reply'


@pytest.mark.asyncio
async def test_kook_get_gateway_redacts_token_in_platform_api_result():
    adapter = make_adapter()
    adapter._request = AsyncMock(
        return_value={
            'code': 0,
            'data': {
                'url': 'wss://example.invalid/gateway?compress=1&token=secret-token',
            },
        }
    )

    result = await get_gateway(adapter, {'compress': 1})

    assert result['data']['url'] == 'wss://example.invalid/gateway?compress=1&token=%3Credacted%3E'
    assert 'secret-token' not in result['data']['url']


@pytest.mark.asyncio
async def test_kook_handle_event_dispatches_eba_and_legacy_then_caches():
    adapter = make_adapter()
    adapter.bot_account_id = 'bot'
    calls: list[str] = []

    async def legacy_listener(event, adapter):
        calls.append(type(event).__name__)

    async def eba_listener(event, adapter):
        calls.append(event.type)

    adapter.register_listener(platform_events.GroupMessage, legacy_listener)
    adapter.register_listener(platform_events.MessageReceivedEvent, eba_listener)

    await adapter._handle_event(fake_kook_message(), 7)

    assert calls == ['GroupMessage', 'message.received']
    assert adapter.current_sn == 7
    assert 'm1' in adapter._message_cache
    assert 'u1' in adapter._user_cache
    assert 'c1' in adapter._group_cache
