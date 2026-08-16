from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.wecom_customer_service_api.api import WecomCSClient
from langbot.libs.wecom_customer_service_api.wecomcsevent import WecomCSEvent
from langbot.pkg.platform.adapters.wecomcs.adapter import WecomCSAdapter
from langbot.pkg.platform.adapters.wecomcs.event_converter import WecomCSEventConverter
from langbot.pkg.platform.adapters.wecomcs.message_converter import WecomCSMessageConverter, split_string_by_bytes
from langbot.pkg.platform.adapters.wecomcs.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


class DummyWecomCSClient(WecomCSClient):
    def __init__(self, *args, **kwargs):
        self.corpid = kwargs['corpid']
        self.secret = kwargs['secret']
        self.token = kwargs['token']
        self.aes = kwargs['EncodingAESKey']
        self.base_url = kwargs.get('api_base_url', 'https://qyapi.weixin.qq.com/cgi-bin')
        self.logger = kwargs.get('logger')
        self.access_token = ''
        self._message_handlers = {}
        self.get_media_id = AsyncMock(return_value='media-id')
        self.send_text_msg = AsyncMock(return_value={'msgid': 'sent-text'})
        self.send_image_msg = AsyncMock(return_value={'msgid': 'sent-image'})
        self.get_customer_info = AsyncMock(
            return_value={'external_userid': 'external-1', 'nickname': 'Alice', 'avatar': 'https://example.test/a.png'}
        )
        self.check_access_token = AsyncMock(return_value=True)
        self.get_access_token = AsyncMock(return_value='access-token')
        self.handle_unified_webhook = AsyncMock(return_value='success')

    def on_message(self, msg_type: str):
        def decorator(func):
            self._message_handlers.setdefault(msg_type, []).append(func)
            return func

        return decorator


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'wecomcs'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def make_adapter() -> WecomCSAdapter:
    config = {
        'corpid': 'corp-id',
        'secret': 'secret',
        'token': 'token',
        'EncodingAESKey': 'encoding-key',
        'api_base_url': 'https://qyapi.weixin.qq.com/cgi-bin',
    }
    with patch('langbot.pkg.platform.adapters.wecomcs.adapter.WecomCSClient', DummyWecomCSClient):
        return WecomCSAdapter(config, DummyLogger())


def wecomcs_event(**overrides) -> WecomCSEvent:
    msgtype = overrides.get('msgtype', 'text')
    payload = {
        'msgtype': msgtype,
        'msgid': overrides.get('message_id', 'msg-1'),
        'external_userid': overrides.get('external_userid', 'external-1'),
        'open_kfid': overrides.get('open_kfid', 'kf-1'),
        'send_time': overrides.get('send_time', 1_714_000_000),
    }
    if msgtype == 'text':
        payload['text'] = {'content': overrides.get('content', 'hello')}
    if msgtype == 'image':
        payload['image'] = {'media_id': overrides.get('media_id', 'media-id')}
        payload['picurl'] = overrides.get('picurl', 'data:image/png;base64,AAAA')
    if msgtype == 'file':
        payload['file'] = {'media_id': 'file-id', 'filename': 'a.txt', 'file_size': 12}
    if msgtype == 'voice':
        payload['voice'] = {'media_id': 'voice-id'}
    return WecomCSEvent.from_payload(payload)


def test_wecomcs_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_wecomcs_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_wecomcs_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


def test_wecomcs_split_string_by_bytes_keeps_multibyte_boundaries():
    parts = split_string_by_bytes('你好hello', limit=7)

    assert ''.join(parts) == '你好hello'
    assert all(len(part.encode('utf-8')) <= 7 for part in parts)


@pytest.mark.asyncio
async def test_wecomcs_message_converter_maps_outbound_components():
    adapter = make_adapter()
    content = await WecomCSMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi'),
                platform_message.Image(base64='data:image/png;base64,AAAA'),
                platform_message.Quote(
                    id='origin',
                    origin=platform_message.MessageChain([platform_message.Plain(text='quoted')]),
                ),
                platform_message.At(target='external-2', display='Bob'),
                platform_message.AtAll(),
            ]
        ),
        adapter.bot,
    )

    assert content[0] == {'type': 'text', 'content': 'hi'}
    assert {'type': 'image', 'media_id': 'media-id'} in content
    assert {'type': 'text', 'content': '[Quote origin] '} in content
    assert {'type': 'text', 'content': 'quoted'} in content
    assert {'type': 'text', 'content': '@Bob'} in content
    assert {'type': 'text', 'content': '@all'} in content


@pytest.mark.asyncio
async def test_wecomcs_message_converter_rejects_unsupported_outbound_media():
    adapter = make_adapter()

    with pytest.raises(NotSupportedError):
        await WecomCSMessageConverter.yiri2target(
            platform_message.MessageChain([platform_message.Voice(base64='BBBB')]),
            adapter.bot,
        )


@pytest.mark.asyncio
async def test_wecomcs_event_converter_maps_text_message_to_eba_and_legacy():
    adapter = make_adapter()
    event = await WecomCSEventConverter.target2yiri(wecomcs_event(), adapter.bot)

    assert isinstance(event, platform_events.MessageReceivedEvent)
    assert event.adapter_name == 'wecomcs-eba'
    assert event.chat_type == platform_entities.ChatType.PRIVATE
    assert event.chat_id == 'external-1|kf-1'
    assert event.sender.nickname == 'Alice'
    assert str(event.message_chain) == 'hello'

    legacy = await WecomCSEventConverter.target2legacy(wecomcs_event(), adapter.bot)
    assert isinstance(legacy, platform_events.FriendMessage)
    assert legacy.sender.id == 'external-1'
    assert str(legacy.message_chain) == 'hello'


@pytest.mark.asyncio
async def test_wecomcs_event_converter_maps_media_and_unknown_messages():
    image_event = await WecomCSEventConverter.target2yiri(wecomcs_event(msgtype='image'), make_adapter().bot)
    file_event = await WecomCSEventConverter.target2yiri(wecomcs_event(msgtype='file'), make_adapter().bot)
    voice_event = await WecomCSEventConverter.target2yiri(wecomcs_event(msgtype='voice'), make_adapter().bot)
    unknown_event = await WecomCSEventConverter.target2yiri(wecomcs_event(msgtype='event'), make_adapter().bot)

    assert isinstance(image_event.message_chain[1], platform_message.Image)
    assert image_event.message_chain[1].base64 == 'data:image/png;base64,AAAA'
    assert isinstance(file_event.message_chain[1], platform_message.File)
    assert isinstance(voice_event.message_chain[1], platform_message.Voice)
    assert isinstance(unknown_event, platform_events.PlatformSpecificEvent)
    assert unknown_event.action == 'wecomcs.event'


@pytest.mark.asyncio
async def test_wecomcs_adapter_dispatches_eba_and_legacy_and_caches_message_event():
    adapter = make_adapter()
    eba_calls: list[platform_events.Event] = []
    legacy_calls: list[platform_events.Event] = []

    async def eba_listener(event, adapter):
        eba_calls.append(event)

    async def legacy_listener(event, adapter):
        legacy_calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, eba_listener)
    adapter.register_listener(platform_events.FriendMessage, legacy_listener)
    await adapter._handle_native_event(wecomcs_event())

    assert len(eba_calls) == 1
    assert len(legacy_calls) == 1
    received = eba_calls[0]
    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert adapter.bot_account_id == 'kf-1'
    assert await adapter.get_message('private', 'external-1|kf-1', 'msg-1') == received
    assert (await adapter.get_user_info('external-1')).nickname == 'Alice'

    await adapter._handle_native_event(wecomcs_event())
    assert len(eba_calls) == 1
    assert len(legacy_calls) == 1


@pytest.mark.asyncio
async def test_wecomcs_send_reply_and_platform_api_use_underlying_client():
    adapter = make_adapter()
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    await adapter.send_message('person', 'external-1|kf-1', message)
    adapter.bot.send_text_msg.assert_awaited_once()
    open_kfid, external_userid, msgid, content = adapter.bot.send_text_msg.await_args.args
    assert (open_kfid, external_userid, content) == ('kf-1', 'external-1', 'hello')
    assert msgid.startswith('lb-')

    image = platform_message.MessageChain([platform_message.Image(base64='data:image/png;base64,AAAA')])
    await adapter.send_message('person', 'external-1|kf-1', image)
    adapter.bot.send_image_msg.assert_awaited_once()

    source_event = await WecomCSEventConverter.target2yiri(wecomcs_event(), adapter.bot)
    await adapter.reply_message(source_event, message)
    open_kfid, external_userid, reply_msgid, content = adapter.bot.send_text_msg.await_args.args
    assert (open_kfid, external_userid, content) == ('kf-1', 'external-1', 'hello')
    assert reply_msgid.startswith('lb-')

    token_status = await adapter.call_platform_api('check_access_token', {})
    customer_info = await adapter.call_platform_api('get_customer_info', {'external_userid': 'external-1'})

    assert token_status == {'valid': True}
    assert customer_info['nickname'] == 'Alice'
