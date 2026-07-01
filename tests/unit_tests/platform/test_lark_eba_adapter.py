from __future__ import annotations

import pathlib
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.pkg.platform.adapters.lark.adapter import LarkAdapter
from langbot.pkg.platform.adapters.lark.event_converter import LarkEventConverter
from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot.pkg.platform.adapters.lark.platform_api import PLATFORM_API_MAP
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


class DummyResponse:
    def __init__(self, data=None, ok=True):
        self.data = data or SimpleNamespace(message_id='reply-msg')
        self.code = 0 if ok else 1
        self.msg = 'ok' if ok else 'failed'
        self.raw = SimpleNamespace(content='{}', headers={'content-type': 'text/plain'})
        self.file = SimpleNamespace(read=lambda: b'data')
        self._ok = ok

    def success(self):
        return self._ok

    def get_log_id(self):
        return 'log-id'


def message_item(message_id='msg-remote'):
    return SimpleNamespace(
        message_id=message_id,
        msg_type='text',
        create_time=1_714_000_000_000,
        body=SimpleNamespace(content='{"text":"remote"}'),
        mentions=[],
        chat_id='chat-1',
    )


class DummyAPIClient:
    def __init__(self):
        self.im = SimpleNamespace(
            v1=SimpleNamespace(
                message=SimpleNamespace(
                    acreate=AsyncMock(return_value=DummyResponse()),
                    areply=AsyncMock(return_value=DummyResponse()),
                    aget=AsyncMock(return_value=DummyResponse(SimpleNamespace(items=[]))),
                ),
                chat=SimpleNamespace(
                    aget=AsyncMock(return_value=DummyResponse(SimpleNamespace(chat_id='chat-1', name='LangBot Team')))
                ),
                image=SimpleNamespace(
                    acreate=AsyncMock(return_value=DummyResponse(SimpleNamespace(image_key='img-key')))
                ),
                file=SimpleNamespace(
                    acreate=AsyncMock(return_value=DummyResponse(SimpleNamespace(file_key='file-key')))
                ),
                message_resource=SimpleNamespace(aget=AsyncMock(return_value=DummyResponse())),
            )
        )
        self.auth = SimpleNamespace(
            v3=SimpleNamespace(
                app_ticket=SimpleNamespace(resend=AsyncMock(return_value=DummyResponse())),
                app_access_token=SimpleNamespace(create=AsyncMock(return_value=DummyResponse())),
                tenant_access_token=SimpleNamespace(create=AsyncMock(return_value=DummyResponse())),
            )
        )
        self.cardkit = SimpleNamespace(
            v1=SimpleNamespace(
                card=SimpleNamespace(create=AsyncMock(return_value=DummyResponse(SimpleNamespace(card_id='card-id')))),
                card_element=SimpleNamespace(content=AsyncMock(return_value=DummyResponse())),
            )
        )


class DummyWSClient:
    def __init__(self):
        self._auto_reconnect = True
        self._connect = AsyncMock()
        self._disconnect = AsyncMock()
        self._reconnect = AsyncMock()


def manifest() -> dict:
    path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'lark'
        / 'manifest.yaml'
    )
    return yaml.safe_load(path.read_text())


def make_adapter(config: dict | None = None) -> LarkAdapter:
    adapter = LarkAdapter(
        {
            'app_id': 'cli_xxx',
            'app_secret': 'secret',
            'bot_name': 'LangBotDev',
            'enable-webhook': False,
            'enable-stream-reply': False,
            'app_type': 'self',
            **(config or {}),
        },
        DummyLogger(),
    )
    adapter.api_client = DummyAPIClient()
    adapter.bot = DummyWSClient()
    return adapter


def lark_event(chat_type='group', message_type='text', content=None):
    message = SimpleNamespace(
        message_id='msg-1',
        message_type=message_type,
        content=content or '{"text":"hello @_user_1"}',
        create_time=1_714_000_000_000,
        mentions=[SimpleNamespace(key='@_user_1', id='user-mention', name='Alice')],
        chat_type=chat_type,
        chat_id='chat-1',
        parent_id=None,
        thread_id=None,
    )
    sender = SimpleNamespace(sender_id=SimpleNamespace(open_id='user-1', union_id='Alice Union'))
    header = SimpleNamespace(tenant_key='tenant-1')
    return SimpleNamespace(event=SimpleNamespace(message=message, sender=sender), header=header, schema='2.0')


def test_lark_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_lark_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_lark_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_lark_message_converter_maps_outbound_components():
    with (
        patch.object(LarkMessageConverter, 'upload_image_to_lark', AsyncMock(return_value='img-key')),
        patch.object(LarkMessageConverter, 'upload_file_to_lark', AsyncMock(return_value='file-key')),
        patch.object(LarkMessageConverter, '_get_component_bytes', AsyncMock(return_value=b'data')),
    ):
        text_elements, media_items = await LarkMessageConverter.yiri2target(
            platform_message.MessageChain(
                [
                    platform_message.Plain(text='hello\n\nsecond'),
                    platform_message.At(target='ou_user', display='Alice'),
                    platform_message.AtAll(),
                    platform_message.Image(base64='ZGF0YQ=='),
                    platform_message.Voice(base64='ZGF0YQ==', length=2),
                    platform_message.File(name='doc.txt', base64='ZGF0YQ=='),
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
            ),
            DummyAPIClient(),
        )

    assert any(ele.get('text') == 'hello' for paragraph in text_elements for ele in paragraph)
    assert any(ele.get('user_id') == 'ou_user' for paragraph in text_elements for ele in paragraph)
    assert any(ele.get('user_id') == 'all' for paragraph in text_elements for ele in paragraph)
    assert {'msg_type': 'image', 'content': {'image_key': 'img-key'}} in media_items
    assert {'msg_type': 'audio', 'content': {'file_key': 'file-key'}} in media_items
    assert {'msg_type': 'file', 'content': {'file_key': 'file-key'}} in media_items


@pytest.mark.asyncio
async def test_lark_message_converter_maps_inbound_components():
    with patch.object(
        LarkMessageConverter,
        '_download_resource',
        AsyncMock(
            return_value={
                'url': 'file:///tmp/file',
                'path': '/tmp/file',
                'base64': 'data:text/plain;base64,ZGF0YQ==',
                'size': 4,
            }
        ),
    ):
        text_chain = await LarkMessageConverter.target2yiri(lark_event().event.message, DummyAPIClient())
        image_chain = await LarkMessageConverter.target2yiri(
            lark_event(message_type='image', content='{"image_key":"img-key"}').event.message, DummyAPIClient()
        )
        file_chain = await LarkMessageConverter.target2yiri(
            lark_event(message_type='file', content='{"file_key":"file-key","file_name":"doc.txt"}').event.message,
            DummyAPIClient(),
        )

    assert isinstance(text_chain[0], platform_message.Source)
    assert isinstance(text_chain[1], platform_message.Plain)
    assert isinstance(text_chain[2], platform_message.At)
    assert text_chain[2].target == 'user-mention'
    assert isinstance(image_chain[1], platform_message.Image)
    assert image_chain[1].image_id == 'img-key'
    assert isinstance(file_chain[1], platform_message.File)
    assert file_chain[1].name == 'doc.txt'


@pytest.mark.asyncio
async def test_lark_event_converter_maps_group_and_private_message():
    group_event = await LarkEventConverter.target2yiri(lark_event('group'), DummyAPIClient())

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.adapter_name == 'lark-eba'
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 'chat-1'
    assert group_event.group.id == 'chat-1'
    assert group_event.sender.id == 'user-1'

    private_event = await LarkEventConverter.target2yiri(
        lark_event('p2p', content='{"text":"hello"}'),
        DummyAPIClient(),
    )
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 'user-1'
    assert private_event.group is None


@pytest.mark.asyncio
async def test_lark_adapter_dispatches_and_caches_message_event():
    adapter = make_adapter()
    calls: list[platform_events.Event] = []

    async def listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, listener)
    await adapter._handle_message_event(lark_event())

    assert len(calls) == 1
    received = calls[0]
    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert await adapter.get_message('group', 'chat-1', 'msg-1') == received
    assert (await adapter.get_group_info('chat-1')).name == ''
    assert (await adapter.get_user_info('user-1')).nickname == 'Alice Union'


@pytest.mark.asyncio
async def test_lark_get_message_fetches_uncached_message():
    adapter = make_adapter()
    adapter.api_client.im.v1.message.aget = AsyncMock(
        return_value=DummyResponse(SimpleNamespace(items=[message_item('msg-remote')]))
    )

    event = await adapter.get_message('group', 'chat-1', 'msg-remote')

    assert event.adapter_name == 'lark-eba'
    assert event.message_id == 'msg-remote'
    assert event.chat_type == platform_entities.ChatType.GROUP
    assert isinstance(event.message_chain[1], platform_message.Plain)
    assert event.message_chain[1].text == 'remote'


@pytest.mark.asyncio
async def test_lark_send_reply_platform_api_and_modes():
    adapter = make_adapter()
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    sent = await adapter.send_message('group', 'chat-1', message)
    assert sent.raw['message_ids'] == ['reply-msg']
    adapter.api_client.im.v1.message.acreate.assert_awaited_once()

    source_event = await LarkEventConverter.target2yiri(lark_event(), adapter.api_client)
    replied = await adapter.reply_message(source_event, message)
    assert replied.raw['message_ids'] == ['reply-msg']
    adapter.api_client.im.v1.message.areply.assert_awaited_once()

    assert await adapter.call_platform_api('check_tenant_access_token', {}) == {'ok': True}

    await adapter.run_async()
    adapter.bot._connect.assert_awaited_once()

    webhook_adapter = make_adapter({'enable-webhook': True})
    task = asyncio.create_task(webhook_adapter.run_async())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    webhook_adapter.bot._connect.assert_not_awaited()
