from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.wecom_api.api import WecomClient
from langbot.libs.wecom_api.wecomevent import WecomEvent
from langbot.pkg.platform.adapters.wecom.adapter import WecomAdapter
from langbot.pkg.platform.adapters.wecom.event_converter import WecomEventConverter
from langbot.pkg.platform.adapters.wecom.message_converter import WecomMessageConverter, split_string_by_bytes
from langbot.pkg.platform.adapters.wecom.platform_api import PLATFORM_API_MAP
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


class DummyWecomClient(WecomClient):
    def __init__(self, *args, **kwargs):
        self.corpid = kwargs['corpid']
        self.secret = kwargs['secret']
        self.token = kwargs['token']
        self.aes = kwargs['EncodingAESKey']
        self.secret_for_contacts = kwargs.get('contacts_secret', '')
        self.base_url = kwargs.get('api_base_url', 'https://qyapi.weixin.qq.com/cgi-bin')
        self.logger = kwargs.get('logger')
        self.access_token = ''
        self._message_handlers = {}
        self.get_media_id = AsyncMock(return_value='media-id')
        self.send_private_msg = AsyncMock()
        self.send_image = AsyncMock()
        self.send_voice = AsyncMock()
        self.send_file = AsyncMock()
        self.get_user_info = AsyncMock(return_value={'userid': 'user-1', 'name': 'Alice', 'alias': 'alice'})
        self.check_access_token = AsyncMock(return_value=True)
        self.get_access_token = AsyncMock(return_value='access-token')
        self.send_to_all = AsyncMock()
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
        / 'wecom'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def make_adapter() -> WecomAdapter:
    config = {
        'corpid': 'corp-id',
        'secret': 'secret',
        'token': 'token',
        'EncodingAESKey': 'encoding-key',
        'contacts_secret': 'contacts-secret',
        'api_base_url': 'https://qyapi.weixin.qq.com/cgi-bin',
    }
    with patch('langbot.pkg.platform.adapters.wecom.adapter.WecomClient', DummyWecomClient):
        return WecomAdapter(config, DummyLogger())


def wecom_event(**overrides) -> WecomEvent:
    payload = {
        'ToUserName': overrides.get('to_user', 'corp-id'),
        'FromUserName': overrides.get('from_user', 'user-1'),
        'CreateTime': overrides.get('create_time', 1_714_000_000),
        'MsgType': overrides.get('msg_type', 'text'),
        'Content': overrides.get('content', 'hello'),
        'MsgId': overrides.get('message_id', 12345),
        'AgentID': overrides.get('agent_id', 1000002),
    }
    if payload['MsgType'] == 'image':
        payload['MediaId'] = overrides.get('media_id', 'media-id')
        payload['PicUrl'] = overrides.get('picurl', 'https://example.test/a.png')
    return WecomEvent.from_payload(payload)


def test_wecom_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_wecom_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_wecom_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


def test_wecom_split_string_by_bytes_keeps_multibyte_boundaries():
    parts = split_string_by_bytes('你好hello', limit=7)

    assert ''.join(parts) == '你好hello'
    assert all(len(part.encode('utf-8')) <= 7 for part in parts)


@pytest.mark.asyncio
async def test_wecom_message_converter_maps_outbound_components():
    adapter = make_adapter()
    content = await WecomMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi'),
                platform_message.Image(base64='data:image/png;base64,AAAA'),
                platform_message.Voice(base64='data:audio/mp3;base64,BBBB'),
                platform_message.File(name='doc.txt', base64='Q0NDQw=='),
                platform_message.Quote(
                    id='origin',
                    origin=platform_message.MessageChain([platform_message.Plain(text='quoted')]),
                ),
            ]
        ),
        adapter.bot,
    )

    assert content[0] == {'type': 'text', 'content': 'hi'}
    assert {'type': 'image', 'media_id': 'media-id'} in content
    assert {'type': 'voice', 'media_id': 'media-id'} in content
    assert {'type': 'file', 'media_id': 'media-id'} in content
    assert {'type': 'text', 'content': '[Quote origin] '} in content
    assert {'type': 'text', 'content': 'quoted'} in content


@pytest.mark.asyncio
async def test_wecom_event_converter_maps_text_message_to_eba_and_legacy():
    adapter = make_adapter()
    event = await WecomEventConverter.target2yiri(wecom_event(), adapter.bot)

    assert isinstance(event, platform_events.MessageReceivedEvent)
    assert event.adapter_name == 'wecom-eba'
    assert event.chat_type == platform_entities.ChatType.PRIVATE
    assert event.chat_id == 'user-1|1000002'
    assert event.sender.nickname == 'Alice'
    assert str(event.message_chain) == 'hello'

    legacy = await WecomEventConverter.target2legacy(wecom_event(), adapter.bot)
    assert isinstance(legacy, platform_events.FriendMessage)
    assert legacy.sender.id == 'user-1'
    assert str(legacy.message_chain) == 'hello'


@pytest.mark.asyncio
async def test_wecom_event_converter_maps_image_message_to_eba():
    adapter = make_adapter()

    with patch(
        'langbot.pkg.platform.adapters.wecom.message_converter.image.get_wecom_image_base64',
        AsyncMock(return_value=('AAAA', 'png')),
    ):
        event = await WecomEventConverter.target2yiri(
            wecom_event(msg_type='image', content=None, picurl='https://example.test/a.png'),
            adapter.bot,
        )

    assert isinstance(event, platform_events.MessageReceivedEvent)
    assert event.adapter_name == 'wecom-eba'
    assert event.message_id == 12345
    assert isinstance(event.message_chain[1], platform_message.Image)
    assert event.message_chain[1].base64 == 'data:image/png;base64,AAAA'


@pytest.mark.asyncio
async def test_wecom_adapter_dispatches_and_caches_message_event():
    adapter = make_adapter()
    calls: list[platform_events.Event] = []

    async def listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, listener)
    await adapter._handle_native_event(wecom_event())

    assert len(calls) == 1
    received = calls[0]
    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert adapter.bot_account_id == 'corp-id'
    assert received.chat_id == 'user-1|1000002'
    assert await adapter.get_message('private', 'user-1|1000002', 12345) == received
    assert (await adapter.get_user_info('user-1')).nickname == 'Alice'


@pytest.mark.asyncio
async def test_wecom_send_reply_and_platform_api_use_underlying_client():
    adapter = make_adapter()
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    await adapter.send_message('person', 'user-1|1000002', message)
    adapter.bot.send_private_msg.assert_awaited_once_with('user-1', 1000002, 'hello')

    source_event = await WecomEventConverter.target2yiri(wecom_event(), adapter.bot)
    await adapter.reply_message(source_event, message)
    assert adapter.bot.send_private_msg.await_count == 2

    token_status = await adapter.call_platform_api('check_access_token', {})
    user_info = await adapter.call_platform_api('get_user_info', {'user_id': 'user-1'})
    sent_all = await adapter.call_platform_api('send_to_all', {'content': 'notice', 'agent_id': 1000002})

    assert token_status == {'valid': True}
    assert user_info['name'] == 'Alice'
    assert sent_all == {'ok': True}
