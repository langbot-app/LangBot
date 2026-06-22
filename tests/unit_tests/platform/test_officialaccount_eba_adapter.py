from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.official_account_api.oaevent import OAEvent
from langbot.pkg.platform.adapters.officialaccount.adapter import OfficialAccountAdapter
from langbot.pkg.platform.adapters.officialaccount.errors import NotSupportedError
from langbot.pkg.platform.adapters.officialaccount.event_converter import OfficialAccountEventConverter
from langbot.pkg.platform.adapters.officialaccount.message_converter import OfficialAccountMessageConverter
from langbot.pkg.platform.adapters.officialaccount.platform_api import PLATFORM_API_MAP
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


class DummyOAClient:
    def __init__(self, *args, **kwargs):
        self.token = kwargs['token']
        self.aes = kwargs['EncodingAESKey']
        self.appid = kwargs['AppID']
        self.appsecret = kwargs['Appsecret']
        self.base_url = kwargs.get('api_base_url')
        self._message_handlers = {}
        self.generated_content = {}
        self.handle_unified_webhook = AsyncMock(return_value='success')
        self.set_message = AsyncMock(return_value=None)

    def on_message(self, msg_type: str):
        def decorator(func):
            self._message_handlers.setdefault(msg_type, []).append(func)
            return func

        return decorator


class DummyLongerOAClient(DummyOAClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_message = kwargs['LoadingMessage']
        self.msg_queue = {}


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'officialaccount'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def make_adapter(mode: str = 'drop') -> OfficialAccountAdapter:
    config = {
        'token': 'token',
        'EncodingAESKey': 'encoding-key',
        'AppSecret': 'secret',
        'AppID': 'app-id',
        'Mode': mode,
        'LoadingMessage': 'loading',
    }
    with (
        patch('langbot.pkg.platform.adapters.officialaccount.adapter.OAClient', DummyOAClient),
        patch('langbot.pkg.platform.adapters.officialaccount.adapter.OAClientForLongerResponse', DummyLongerOAClient),
    ):
        return OfficialAccountAdapter(config, DummyLogger())


def oa_event(**overrides) -> OAEvent:
    payload = {
        'ToUserName': overrides.get('to_user', 'gh_app'),
        'FromUserName': overrides.get('from_user', 'openid-1'),
        'CreateTime': overrides.get('timestamp', 1710000000),
        'MsgType': overrides.get('msgtype', 'text'),
        'Content': overrides.get('content', 'hello'),
        'MsgId': overrides.get('message_id', 123),
    }
    if payload['MsgType'] == 'image':
        payload.update({'PicUrl': 'https://example.test/a.jpg', 'MediaId': 'media-1', 'Content': None})
    if payload['MsgType'] == 'voice':
        payload.update({'MediaId': 'voice-1', 'Content': None})
    if payload['MsgType'] == 'event':
        payload.update({'Event': overrides.get('event', 'subscribe'), 'EventKey': 'qrscene_1', 'Content': None})
    return OAEvent(payload)


def test_officialaccount_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_officialaccount_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_officialaccount_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_officialaccount_message_converter_maps_components_to_passive_text():
    content = await OfficialAccountMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi'),
                platform_message.Image(url='https://example.test/a.png'),
                platform_message.File(name='a.txt', url='https://example.test/a.txt'),
                platform_message.Quote(origin=platform_message.MessageChain([platform_message.Plain(text='quoted')])),
            ]
        )
    )

    assert 'hi' in content
    assert '[Image]' in content
    assert '[File: a.txt]' in content
    assert 'quoted' in content


@pytest.mark.asyncio
async def test_officialaccount_event_converter_maps_text_image_voice_and_platform_event():
    text_event = await OfficialAccountEventConverter().target2yiri(oa_event(content='hello'))
    image_event = await OfficialAccountEventConverter().target2yiri(oa_event(msgtype='image'))
    voice_event = await OfficialAccountEventConverter().target2yiri(oa_event(msgtype='voice'))
    subscribe_event = await OfficialAccountEventConverter().target2yiri(oa_event(msgtype='event', event='subscribe'))

    assert isinstance(text_event, platform_events.MessageReceivedEvent)
    assert text_event.adapter_name == 'officialaccount-eba'
    assert text_event.chat_type == platform_entities.ChatType.PRIVATE
    assert text_event.chat_id == 'openid-1'
    assert str(text_event.message_chain) == 'hello'

    assert isinstance(image_event.message_chain[1], platform_message.Image)
    assert image_event.message_chain[1].image_id == 'media-1'
    assert isinstance(voice_event.message_chain[1], platform_message.Voice)
    assert voice_event.message_chain[1].voice_id == 'voice-1'
    assert isinstance(subscribe_event, platform_events.PlatformSpecificEvent)
    assert subscribe_event.action == 'officialaccount.subscribe'


@pytest.mark.asyncio
async def test_officialaccount_adapter_dispatches_eba_and_legacy_and_caches_message_event():
    adapter = make_adapter()
    eba_calls: list[platform_events.Event] = []
    legacy_calls: list[platform_events.Event] = []

    async def eba_listener(event, adapter):
        eba_calls.append(event)

    async def legacy_listener(event, adapter):
        legacy_calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, eba_listener)
    adapter.register_listener(platform_events.FriendMessage, legacy_listener)
    await adapter._handle_native_event(oa_event())

    assert len(eba_calls) == 1
    assert len(legacy_calls) == 1
    received = eba_calls[0]
    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert await adapter.get_message('private', 'openid-1', 123) == received
    assert (await adapter.get_user_info('openid-1')).nickname == 'openid-1'


@pytest.mark.asyncio
async def test_officialaccount_reply_platform_api_and_unsupported_send():
    adapter = make_adapter()
    source_event = await OfficialAccountEventConverter().target2yiri(oa_event())
    message = platform_message.MessageChain([platform_message.Plain(text='reply')])

    await adapter.reply_message(source_event, message)
    adapter.bot.set_message.assert_awaited_once_with(123, 'reply')

    assert await adapter.call_platform_api('get_mode', {}) == {'mode': 'drop', 'longer_response': False}

    with pytest.raises(NotSupportedError):
        await adapter.send_message('person', 'openid-1', message)


@pytest.mark.asyncio
async def test_officialaccount_passive_mode_reply_queues_by_user():
    adapter = make_adapter(mode='passive')
    source_event = await OfficialAccountEventConverter().target2yiri(oa_event())

    await adapter.reply_message(source_event, platform_message.MessageChain([platform_message.Plain(text='reply')]))

    adapter.bot.set_message.assert_awaited_once_with('openid-1', 123, 'reply')
