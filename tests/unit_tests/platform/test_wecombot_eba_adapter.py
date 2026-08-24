from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot.pkg.platform.adapters.wecombot.adapter import WecomBotAdapter
from langbot.pkg.platform.adapters.wecombot.event_converter import WecomBotEventConverter
from langbot.pkg.platform.adapters.wecombot.message_converter import WecomBotMessageConverter
from langbot.pkg.platform.adapters.wecombot.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.wecombot.interaction import (
    build_interaction_card,
    interaction_event_from_native,
)
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


class DummyWecomBotWsClient:
    def __init__(self, *args, **kwargs):
        self.bot_id = kwargs['bot_id']
        self.secret = kwargs['secret']
        self.encoding_aes_key = kwargs.get('encoding_aes_key', '')
        self._message_handlers = {}
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.send_message = AsyncMock(return_value={'ok': True})
        self.reply_text = AsyncMock(return_value={'reply': True})
        self.push_stream_chunk = AsyncMock(return_value=True)
        self.set_message = AsyncMock(return_value={'set': True})
        self.send_template_card = AsyncMock(return_value={'sent': True})

    def on_message(self, msg_type: str):
        def decorator(func):
            self._message_handlers.setdefault(msg_type, []).append(func)
            return func

        return decorator

    def on_feedback(self):
        def decorator(func):
            self._message_handlers.setdefault('feedback', []).append(func)
            return func

        return decorator


class DummyWecomBotClient(DummyWecomBotWsClient):
    def __init__(self, *args, **kwargs):
        self.Token = kwargs['Token']
        self.EnCodingAESKey = kwargs['EnCodingAESKey']
        self.Corpid = kwargs['Corpid']
        self._message_handlers = {}
        self.handle_unified_webhook = AsyncMock(return_value='success')
        self.push_stream_chunk = AsyncMock(return_value=True)
        self.set_message = AsyncMock(return_value={'set': True})


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'wecombot'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text(encoding='utf-8'))


def make_adapter(enable_webhook: bool = False) -> WecomBotAdapter:
    config = {
        'BotId': 'bot-id',
        'robot_name': 'EBA Bot',
        'enable-webhook': enable_webhook,
        'Secret': 'secret',
        'Token': 'token',
        'EncodingAESKey': 'encoding-key',
        'Corpid': 'corp-id',
        'enable-stream-reply': True,
    }
    with (
        patch('langbot.pkg.platform.adapters.wecombot.adapter.WecomBotWsClient', DummyWecomBotWsClient),
        patch('langbot.pkg.platform.adapters.wecombot.adapter.WecomBotClient', DummyWecomBotClient),
    ):
        return WecomBotAdapter(config, DummyLogger())


def wecombot_event(**overrides) -> WecomBotEvent:
    event_type = overrides.get('type', 'single')
    payload = {
        'type': event_type,
        'msgtype': overrides.get('msgtype', 'text'),
        'msgid': overrides.get('message_id', 'msg-1'),
        'userid': overrides.get('userid', 'user-1'),
        'username': overrides.get('username', 'Alice'),
        'content': overrides.get('content', 'hello'),
        'aibotid': overrides.get('aibotid', 'bot-id'),
        'req_id': overrides.get('req_id', 'req-1'),
        'stream_id': overrides.get('stream_id', 'stream-1'),
    }
    if event_type == 'group':
        payload.update({'chatid': overrides.get('chatid', 'group-1'), 'chatname': overrides.get('chatname', 'Group')})
    if payload['msgtype'] == 'image':
        payload['images'] = overrides.get('images', ['data:image/png;base64,AAAA'])
        payload['content'] = overrides.get('content', '')
    if payload['msgtype'] == 'file':
        payload['file'] = overrides.get('file', {'download_url': 'https://example.test/a.txt', 'filename': 'a.txt'})
        payload['content'] = overrides.get('content', '')
    if payload['msgtype'] == 'voice':
        payload['voice'] = overrides.get('voice', {'base64': 'BBBB'})
        payload['content'] = overrides.get('content', '')
    if 'quote' in overrides:
        payload['quote'] = overrides['quote']
    return WecomBotEvent(payload)


def test_wecombot_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_wecombot_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_wecombot_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


def test_wecombot_interaction_card_uses_host_callback_token_and_index():
    card = build_interaction_card(
        {'title': 'Approve?', 'actions': [{'id': 'approve', 'label': 'Approve'}]},
        'callback-token',
    )

    button = card['template_card']['button_list'][0]
    assert button['key'] == 'lbi:callback-token:a:0'


@pytest.mark.asyncio
async def test_wecombot_interaction_delivery_and_callback_event():
    adapter = make_adapter()
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'group', 'target_id': 'group-1'},
            'request': {
                'interaction_id': 'form-1',
                'title': 'Approve?',
                'actions': [{'id': 'approve', 'label': 'Approve'}],
                'fallback_text': 'Reply approve.',
            },
        },
    )

    assert result['rich'] is True
    adapter.bot.send_template_card.assert_awaited_once()

    native = wecombot_event(type='group', msgtype='event')
    native['event'] = {
        'eventtype': 'template_card_event',
        'template_card_event': {'EventKey': 'lbi:callback-token:a:0'},
    }
    event = interaction_event_from_native(native)
    assert event.action == 'interaction.submitted'
    assert event.data['action_ref'] == 0
    assert event.data['target_id'] == 'group-1'

    native['event']['template_card_event'] = {'button': {'key': 'lbi:callback-token:f:0:2'}}
    nested_event = interaction_event_from_native(native)
    assert nested_event.data['field_ref'] == 0
    assert nested_event.data['option_ref'] == 2


@pytest.mark.asyncio
async def test_wecombot_message_converter_maps_outbound_components_to_markdown_text():
    content = await WecomBotMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Plain(text='hi'),
                platform_message.At(target='user-1', display='Alice'),
                platform_message.Image(base64='data:image/png;base64,AAAA'),
                platform_message.File(name='a.txt', url='https://example.test/a.txt'),
                platform_message.Quote(
                    id='origin',
                    origin=platform_message.MessageChain([platform_message.Plain(text='quoted')]),
                ),
            ]
        )
    )

    assert 'hi' in content
    assert '@Alice' in content
    assert '[Image]' in content
    assert '[File: a.txt]' in content
    assert '[Quote origin]' in content
    assert 'quoted' in content


@pytest.mark.asyncio
async def test_wecombot_event_converter_maps_private_and_group_messages_to_eba():
    private_event = await WecomBotEventConverter(bot_name='EBA Bot').target2yiri(
        wecombot_event(content='@EBA Bot hello')
    )
    group_event = await WecomBotEventConverter(bot_name='EBA Bot').target2yiri(
        wecombot_event(type='group', content='@EBA Bot group hello')
    )

    assert isinstance(private_event, platform_events.MessageReceivedEvent)
    assert private_event.adapter_name == 'wecombot-eba'
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 'user-1'
    assert str(private_event.message_chain) == 'hello'

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 'group-1'
    assert group_event.group.name == 'Group'
    assert isinstance(group_event.message_chain[1], platform_message.At)


@pytest.mark.asyncio
async def test_wecombot_event_converter_maps_media_and_quote_components():
    event = await WecomBotEventConverter().target2yiri(
        wecombot_event(
            msgtype='image',
            quote={
                'content': 'quoted',
                'file': {'download_url': 'https://example.test/q.txt', 'filename': 'q.txt'},
            },
        )
    )

    assert isinstance(event, platform_events.MessageReceivedEvent)
    assert any(isinstance(component, platform_message.Image) for component in event.message_chain)
    quote = next(component for component in event.message_chain if isinstance(component, platform_message.Quote))
    assert any(isinstance(component, platform_message.File) for component in quote.origin)


@pytest.mark.asyncio
async def test_wecombot_adapter_dispatches_eba_and_legacy_and_caches_message_event():
    adapter = make_adapter()
    eba_calls: list[platform_events.Event] = []
    legacy_calls: list[platform_events.Event] = []

    async def eba_listener(event, adapter):
        eba_calls.append(event)

    async def legacy_listener(event, adapter):
        legacy_calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, eba_listener)
    adapter.register_listener(platform_events.FriendMessage, legacy_listener)
    await adapter._handle_native_event(wecombot_event())

    assert len(eba_calls) == 1
    assert len(legacy_calls) == 1
    received = eba_calls[0]
    assert isinstance(received, platform_events.MessageReceivedEvent)
    assert await adapter.get_message('private', 'user-1', 'msg-1') == received
    assert (await adapter.get_user_info('user-1')).nickname == 'Alice'


@pytest.mark.asyncio
async def test_wecombot_send_reply_feedback_and_platform_api_use_underlying_client():
    adapter = make_adapter()
    message = platform_message.MessageChain([platform_message.Plain(text='hello')])

    await adapter.send_message('person', 'user-1', message)
    adapter.bot.send_message.assert_awaited_once_with('user-1', 'hello')

    source_event = await WecomBotEventConverter().target2yiri(wecombot_event())
    await adapter.reply_message(source_event, message)
    adapter.bot.reply_text.assert_awaited_once_with('req-1', 'hello')

    await adapter.reply_message_chunk(source_event, None, message, is_final=True)
    adapter.bot.push_stream_chunk.assert_awaited_once_with('msg-1', 'hello', is_final=True)

    platform_status = await adapter.call_platform_api('is_websocket_mode', {})
    assert platform_status == {'websocket': True}

    feedback_calls: list[platform_events.Event] = []

    async def feedback_listener(event, adapter):
        feedback_calls.append(event)

    adapter.register_listener(platform_events.FeedbackReceivedEvent, feedback_listener)
    await adapter._handle_feedback(feedback_id='fb-1', feedback_type=1, inaccurate_reasons=[1, 2], session=None)
    assert isinstance(feedback_calls[0], platform_events.FeedbackReceivedEvent)
    assert feedback_calls[0].inaccurate_reasons == ['1', '2']


@pytest.mark.asyncio
async def test_wecombot_webhook_mode_rejects_proactive_send():
    adapter = make_adapter(enable_webhook=True)
    with pytest.raises(NotSupportedError):
        await adapter.send_message(
            'person', 'user-1', platform_message.MessageChain([platform_message.Plain(text='hi')])
        )
