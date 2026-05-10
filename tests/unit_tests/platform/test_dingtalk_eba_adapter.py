from __future__ import annotations

import pathlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.dingtalk_api.api import DingTalkClient
from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
from langbot.pkg.platform.adapters.dingtalk.adapter import DingTalkAdapter
from langbot.pkg.platform.adapters.dingtalk.event_converter import DingTalkEventConverter
from langbot.pkg.platform.adapters.dingtalk.message_converter import DingTalkMessageConverter
from langbot.pkg.platform.adapters.dingtalk.platform_api import PLATFORM_API_MAP
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


class DummyDingTalkClient(DingTalkClient):
    def __init__(self, *args, **kwargs):
        self._message_handlers = {}
        self.markdown_card = kwargs.get('markdown_card', True)
        self.access_token = ''
        self.send_message = AsyncMock()
        self.send_proactive_message_to_one = AsyncMock(return_value={'ok': True})
        self.send_proactive_message_to_group = AsyncMock(return_value={'ok': True})
        self.get_file_url = AsyncMock(return_value='https://example.test/file')
        self.check_access_token = AsyncMock(return_value=True)
        self.get_access_token = AsyncMock()
        self.get_audio_url = AsyncMock(return_value='data:audio/ogg;base64,AAAA')
        self.download_image = AsyncMock(return_value='data:image/png;base64,BBBB')
        self.create_and_card = AsyncMock(return_value=('card', 'card-id'))
        self.send_card_message = AsyncMock()
        self.start = AsyncMock()
        self.stop = AsyncMock()

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
        / 'dingtalk'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def make_adapter() -> DingTalkAdapter:
    config = {
        'client_id': 'client-id',
        'client_secret': 'client-secret',
        'robot_name': 'LangBot',
        'robot_code': 'robot-code',
        'markdown_card': True,
        'enable-stream-reply': False,
        'card_auto_layout': False,
        'card_template_id': 'template-id',
    }
    with patch('langbot.pkg.platform.adapters.dingtalk.adapter.DingTalkClient', DummyDingTalkClient):
        return DingTalkAdapter(config, DummyLogger())


def dingtalk_event(conversation='GroupMessage', **overrides) -> DingTalkEvent:
    incoming = SimpleNamespace(
        message_id=overrides.get('message_id', 'msg-1'),
        create_at=1_714_000_000_000,
        sender_staff_id=overrides.get('sender_staff_id', 'user-1'),
        sender_nick=overrides.get('sender_nick', 'Alice'),
        conversation_id=overrides.get('conversation_id', 'group-1'),
        conversation_title=overrides.get('conversation_title', 'LangBot Team'),
        chatbot_user_id='robot-dingtalk-id',
        at_users=[SimpleNamespace(dingtalk_id='robot-dingtalk-id')],
    )
    payload = {
        'IncomingMessage': incoming,
        'conversation_type': conversation,
        'Type': overrides.get('msg_type', 'text'),
        'Content': overrides.get('content', '@LangBot hello'),
        'Picture': overrides.get('picture', ''),
        'Audio': overrides.get('audio', ''),
        'File': overrides.get('file', ''),
        'Name': overrides.get('name', ''),
        'QuotedMessage': overrides.get('quoted_message'),
    }
    if 'rich_content' in overrides:
        payload['Rich_Content'] = overrides['rich_content']
    return DingTalkEvent.from_payload(payload)


def test_dingtalk_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_dingtalk_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_dingtalk_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_dingtalk_message_converter_maps_outbound_components():
    content, at = await DingTalkMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi '),
                platform_message.At(target='user-1', display='Alice'),
                platform_message.AtAll(),
                platform_message.Image(url='https://example.test/a.png'),
                platform_message.File(name='doc.txt', url='https://example.test/doc.txt'),
                platform_message.Quote(
                    id='origin', origin=platform_message.MessageChain([platform_message.Plain(text='quoted')])
                ),
                platform_message.Forward(
                    node_list=[
                        platform_message.ForwardMessageNode(
                            sender_id='user-2',
                            sender_name='Bob',
                            message_chain=platform_message.MessageChain([platform_message.Plain(text='node')]),
                        )
                    ]
                ),
            ]
        )
    )

    assert at is True
    assert '@Alice' in content
    assert '@所有人' in content
    assert '![image](https://example.test/a.png)' in content
    assert '[doc.txt](https://example.test/doc.txt)' in content
    assert '[引用消息 origin]' in content
    assert '[Bob] node' in content


@pytest.mark.asyncio
async def test_dingtalk_message_converter_maps_inbound_components():
    event = dingtalk_event(
        file='https://example.test/doc.txt',
        name='doc.txt',
        quoted_message={
            'message_id': 'origin',
            'msg_type': 'text',
            'sender_id': 'user-2',
            'content': 'quoted text',
        },
    )
    chain = await DingTalkMessageConverter.target2yiri(event, 'LangBot')

    assert isinstance(chain[0], platform_message.Source)
    assert isinstance(chain[1], platform_message.At)
    assert isinstance(chain[2], platform_message.Plain)
    assert chain[2].text == ' hello'
    assert isinstance(chain[3], platform_message.File)
    assert isinstance(chain[4], platform_message.Quote)
    assert str(chain[4].origin) == 'quoted text'


@pytest.mark.asyncio
async def test_dingtalk_event_converter_maps_group_and_private_message():
    group_event = await DingTalkEventConverter.target2yiri(dingtalk_event(), 'LangBot')

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.adapter_name == 'dingtalk'
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 'group-1'
    assert group_event.group.name == 'LangBot Team'
    assert group_event.sender.id == 'user-1'

    private_event = await DingTalkEventConverter.target2yiri(
        dingtalk_event('FriendMessage', content='hello'),
        'LangBot',
    )

    assert isinstance(private_event, platform_events.MessageReceivedEvent)
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 'user-1'
    assert private_event.group is None


@pytest.mark.asyncio
async def test_dingtalk_adapter_dispatches_and_caches_message_event():
    adapter = make_adapter()
    calls: list[platform_events.Event] = []

    async def listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, listener)
    event = dingtalk_event()

    await adapter._handle_native_event(event)

    assert len(calls) == 1
    received = calls[0]
    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert await adapter.get_message('group', 'group-1', 'msg-1') == received
    assert (await adapter.get_group_info('group-1')).name == 'LangBot Team'
    assert (await adapter.get_user_info('user-1')).nickname == 'Alice'


@pytest.mark.asyncio
async def test_dingtalk_send_reply_and_platform_api_use_underlying_client():
    adapter = make_adapter()
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    sent = await adapter.send_message('group', 'group-1', message)
    assert sent.raw == {'ok': True}
    adapter.bot.send_proactive_message_to_group.assert_awaited_once()

    source_event = await DingTalkEventConverter.target2yiri(dingtalk_event(), 'LangBot')
    replied = await adapter.reply_message(source_event, message)
    assert replied.message_id == 'msg-1'
    adapter.bot.send_message.assert_awaited_once()

    token_status = await adapter.call_platform_api('check_access_token', {})
    file_url = await adapter.call_platform_api('get_file_url', {'download_code': 'download-code'})

    assert token_status == {'valid': True}
    assert file_url == {'url': 'https://example.test/file'}
