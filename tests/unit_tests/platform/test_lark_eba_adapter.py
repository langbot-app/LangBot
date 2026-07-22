from __future__ import annotations

import json
import pathlib
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from langbot.pkg.platform.adapters.lark.adapter import LarkAdapter
from langbot.pkg.platform.adapters.lark.event_converter import LarkEventConverter
from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot.pkg.platform.adapters.lark.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.lark.interaction import (
    build_interaction_card,
    interaction_delivery_capabilities,
    interaction_event_from_callback,
)
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
                    aupdate=AsyncMock(return_value=DummyResponse()),
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
                card=SimpleNamespace(
                    create=MagicMock(return_value=DummyResponse(SimpleNamespace(card_id='card-id'))),
                    acreate=AsyncMock(return_value=DummyResponse(SimpleNamespace(card_id='card-id'))),
                    aupdate=AsyncMock(return_value=DummyResponse()),
                ),
                card_element=SimpleNamespace(content=MagicMock(return_value=DummyResponse())),
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
    return yaml.safe_load(path.read_text(encoding='utf-8'))


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


def test_lark_interaction_card_uses_host_callback_token_and_indexes():
    card = build_interaction_card(
        {
            'title': 'Approve?',
            'actions': [{'id': 'approve', 'label': 'Approve', 'style': 'primary'}],
        },
        'callback-token',
        {'target_type': 'group', 'target_id': 'chat-1'},
    )

    assert card['schema'] == '2.0'
    button = card['body']['elements'][-1]['columns'][0]['elements'][0]
    assert button['behaviors'][0]['value'] == {'lbi': 'callback-token', 't': 'group', 'ck': 1, 'a': 0}


def test_lark_interaction_card_uses_native_text_input_form():
    card = build_interaction_card(
        {
            'title': 'Add context',
            'fields': [
                {
                    'id': 'comment',
                    'label': 'Comment',
                    'type': 'textarea',
                    'required': True,
                    'placeholder': 'Explain the decision',
                }
            ],
            'actions': [],
        },
        'callback-token',
        {'target_type': 'group', 'target_id': 'chat-1'},
    )

    form = next(element for element in card['body']['elements'] if element['tag'] == 'form')
    field, submit = form['elements']
    assert field['tag'] == 'input'
    assert field['input_type'] == 'multiline_text'
    assert field['required'] is True
    assert submit['form_action_type'] == 'submit'
    assert submit['behaviors'][0]['value'] == {
        'lbi': 'callback-token',
        't': 'group',
        'ck': 1,
        'fm': {'lbi_field_0': 'comment'},
        'ft': {'comment': 'textarea'},
    }


def test_lark_interaction_card_uses_native_select_and_declares_fields():
    card = build_interaction_card(
        {
            'title': 'Priority',
            'fields': [
                {
                    'id': 'priority',
                    'label': 'Priority',
                    'type': 'select',
                    'required': True,
                    'options': [
                        {'value': 'normal', 'label': 'Normal'},
                        {'value': 'urgent', 'label': 'Urgent'},
                    ],
                }
            ],
            'actions': [],
        },
        'callback-token',
        {'target_type': 'person', 'target_id': 'user-1'},
    )

    form = next(element for element in card['body']['elements'] if element['tag'] == 'form')
    label, select, submit = form['elements']
    assert label == {'tag': 'markdown', 'content': '**Priority***'}
    assert select['tag'] == 'select_static'
    assert [option['value'] for option in select['options']] == ['normal', 'urgent']
    assert submit['form_action_type'] == 'submit'
    assert interaction_delivery_capabilities()['field_types'] == ['text', 'textarea', 'number', 'select']
    assert interaction_delivery_capabilities()['supports_updates'] is True


@pytest.mark.asyncio
async def test_lark_interaction_request_sends_interactive_message():
    adapter = make_adapter()

    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'person', 'target_id': 'user-1'},
            'request': {
                'interaction_id': 'form-1',
                'title': 'Approve?',
                'actions': [{'id': 'approve', 'label': 'Approve'}],
                'fallback_text': 'Reply approve.',
            },
        },
    )

    assert result['rich'] is True
    assert result['card_id'] == 'card-id'
    adapter.api_client.cardkit.v1.card.acreate.assert_awaited_once()
    request = adapter.api_client.im.v1.message.acreate.await_args.args[0]
    assert request.receive_id_type == 'open_id'
    assert request.request_body.msg_type == 'interactive'
    assert json.loads(request.request_body.content) == {'type': 'card', 'data': {'card_id': 'card-id'}}


@pytest.mark.asyncio
async def test_lark_interaction_request_updates_existing_message():
    adapter = make_adapter()

    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'next-token',
            'reply_target': {'target_type': 'person', 'target_id': 'user-1'},
            'update_target': {
                'message_id': 'card-message-1',
                'card_id': 'card-id',
                'sequence': 0,
                'rich': True,
            },
            'request': {
                'interaction_id': 'form-2',
                'title': 'Choose action',
                'actions': [{'id': 'approve', 'label': 'Approve'}],
                'fallback_text': 'Reply approve.',
            },
        },
    )

    assert result == {
        'ok': True,
        'message_id': 'card-message-1',
        'card_id': 'card-id',
        'sequence': 1,
        'rich': True,
        'updated': True,
    }
    adapter.api_client.im.v1.message.acreate.assert_not_awaited()
    update_request = adapter.api_client.cardkit.v1.card.aupdate.await_args.args[0]
    assert update_request.card_id == 'card-id'
    assert update_request.request_body.sequence == 1
    card = json.loads(update_request.request_body.card.data)
    assert card['header']['title']['content'] == 'Choose action'
    button = card['body']['elements'][-1]['columns'][0]['elements'][0]
    assert button['behaviors'][0]['value']['lbi'] == 'next-token'


@pytest.mark.asyncio
async def test_lark_interaction_acknowledge_replaces_controls_with_summary():
    adapter = make_adapter()

    result = await adapter.call_platform_api(
        'interaction.acknowledge',
        {
            'update_target': {
                'message_id': 'card-message-1',
                'card_id': 'card-id',
                'sequence': 0,
                'rich': True,
            },
            'request': {
                'title': 'Manual review',
                'fields': [{'id': 'comment', 'label': 'Comment'}],
            },
            'submission': {'values': {'comment': 'Looks good'}},
        },
    )

    assert result['updated'] is True
    update_request = adapter.api_client.cardkit.v1.card.aupdate.await_args.args[0]
    card = json.loads(update_request.request_body.card.data)
    content = card['body']['elements'][-1]['content']
    assert content == '✅ Comment：Looks good'


@pytest.mark.asyncio
async def test_lark_interaction_keeps_prior_values_through_next_action_and_final_acknowledgement():
    adapter = make_adapter()
    update_target = {
        'message_id': 'card-message-1',
        'card_id': 'card-id',
        'sequence': 1,
        'rich': True,
        'submitted_values': [{'label': 'Question', 'value': '123'}],
    }

    action_result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'next-token',
            'reply_target': {'target_type': 'person', 'target_id': 'user-1'},
            'update_target': update_target,
            'request': {
                'interaction_id': 'action-1',
                'title': 'Manual review',
                'actions': [{'id': 'or', 'label': 'or'}],
                'fallback_text': 'Reply or.',
            },
        },
    )

    action_update = adapter.api_client.cardkit.v1.card.aupdate.await_args.args[0]
    action_card = json.loads(action_update.request_body.card.data)
    assert '✅ Question：123' in action_card['body']['elements'][0]['content']
    assert action_result['submitted_values'] == [{'label': 'Question', 'value': '123'}]

    final_result = await adapter.call_platform_api(
        'interaction.acknowledge',
        {
            'update_target': action_result,
            'request': {
                'title': 'Manual review',
                'actions': [{'id': 'or', 'label': 'or'}],
            },
            'submission': {'action_id': 'or', 'values': {}},
        },
    )

    final_update = adapter.api_client.cardkit.v1.card.aupdate.await_args.args[0]
    final_card = json.loads(final_update.request_body.card.data)
    final_content = final_card['body']['elements'][-1]['content']
    assert '✅ Action：or' in final_content
    assert '✅ Question：123' in final_card['body']['elements'][0]['content']
    assert final_result['submitted_values'] == [
        {'label': 'Question', 'value': '123'},
        {'label': 'Action', 'value': 'or'},
    ]


def test_lark_dify_layout_keeps_prompts_next_to_submitted_values():
    prior_values = [
        {
            'description': '11\n请输入你的问题',
            'label': 'us_input',
            'value': '回复我你好',
        }
    ]
    select_card = build_interaction_card(
        {
            'title': '人工介入',
            'description': '请选择你的答案',
            'fields': [
                {
                    'id': 'field_2',
                    'label': 'xiala',
                    'type': 'select',
                    'options': [
                        {'value': '1', 'label': '1'},
                        {'value': '2', 'label': '2'},
                    ],
                }
            ],
            'actions': [],
        },
        'callback-token',
        {'target_type': 'person', 'target_id': 'user-1'},
        prior_values,
    )

    select_elements = select_card['body']['elements']
    assert select_elements[0]['content'] == '11\n请输入你的问题\n✅ us_input：回复我你好'
    assert select_elements[1]['content'] == '请选择你的答案'
    assert select_elements[2]['tag'] == 'form'

    action_card = build_interaction_card(
        {
            'title': '人工介入',
            'description': None,
            'fields': [],
            'actions': [{'id': 'action_1', 'label': 'or'}],
        },
        'callback-token',
        {'target_type': 'person', 'target_id': 'user-1'},
        [
            *prior_values,
            {
                'description': '请选择你的答案',
                'label': 'xiala',
                'value': '1',
            },
        ],
    )

    action_elements = action_card['body']['elements']
    assert [element['content'] for element in action_elements[:2]] == [
        '11\n请输入你的问题\n✅ us_input：回复我你好',
        '请选择你的答案\n✅ xiala：1',
    ]
    assert action_elements[2]['columns'][0]['elements'][0]['text']['content'] == 'or'


def test_lark_message_id_from_card_callback_source():
    adapter = make_adapter()
    callback_source = SimpleNamespace(
        event=SimpleNamespace(context=SimpleNamespace(open_message_id='card-message-1')),
    )

    assert (
        adapter._message_id_from_source(SimpleNamespace(message_id=None, source_platform_object=callback_source))
        == 'card-message-1'
    )
    assert (
        adapter._message_id_from_source(
            SimpleNamespace(
                message_id=None,
                source_platform_object={'event': {'context': {'open_message_id': 'webhook-message-1'}}},
            )
        )
        == 'webhook-message-1'
    )


@pytest.mark.asyncio
async def test_lark_streaming_card_uses_strictly_increasing_sequences():
    adapter = make_adapter()
    adapter.card_id_dict['response-1'] = 'stream-card-1'
    adapter.card_sequence_dict['stream-card-1'] = 0
    adapter.message_converter.yiri2target = AsyncMock(return_value=([[{'tag': 'text', 'text': 'answer'}]], []))
    bot_message = SimpleNamespace(resp_message_id='response-1', msg_sequence=1, tool_calls=None)
    source = SimpleNamespace(source_platform_object=None)
    message = platform_message.MessageChain([platform_message.Plain(text='answer')])

    await adapter.reply_message_chunk(source, bot_message, message)
    first_request = adapter.api_client.cardkit.v1.card_element.content.call_args.args[0]
    assert first_request.request_body.sequence == 1

    bot_message.msg_sequence = 2
    await adapter.reply_message_chunk(source, bot_message, message)
    assert adapter.api_client.cardkit.v1.card_element.content.call_count == 1

    bot_message.msg_sequence = 8
    await adapter.reply_message_chunk(source, bot_message, message)
    second_request = adapter.api_client.cardkit.v1.card_element.content.call_args.args[0]
    assert second_request.request_body.sequence == 2

    bot_message.msg_sequence = 9
    await adapter.reply_message_chunk(source, bot_message, message, is_final=True)
    final_request = adapter.api_client.cardkit.v1.card_element.content.call_args.args[0]
    assert final_request.request_body.sequence == 3
    assert 'response-1' not in adapter.card_id_dict
    assert 'stream-card-1' not in adapter.card_sequence_dict
    assert 'stream-card-1' not in adapter.card_last_update_dict


@pytest.mark.asyncio
async def test_lark_streaming_card_updates_sparse_chunks_without_waiting_for_eighth():
    adapter = make_adapter()
    adapter.card_id_dict['response-1'] = 'stream-card-1'
    adapter.card_sequence_dict['stream-card-1'] = 1
    adapter.card_last_update_dict['stream-card-1'] = time.monotonic() - 2
    adapter.message_converter.yiri2target = AsyncMock(return_value=([[{'tag': 'text', 'text': 'new progress'}]], []))
    bot_message = SimpleNamespace(resp_message_id='response-1', msg_sequence=2, tool_calls=None)
    source = SimpleNamespace(source_platform_object=None)
    message = platform_message.MessageChain([platform_message.Plain(text='new progress')])

    await adapter.reply_message_chunk(source, bot_message, message)

    request = adapter.api_client.cardkit.v1.card_element.content.call_args.args[0]
    assert request.request_body.sequence == 2


@pytest.mark.asyncio
async def test_lark_streaming_card_uses_cumulative_runner_content():
    adapter = make_adapter()
    adapter.card_id_dict['response-1'] = 'stream-card-1'
    adapter.card_sequence_dict['stream-card-1'] = 0
    adapter.message_converter.yiri2target = AsyncMock(
        return_value=([[{'tag': 'text', 'text': 'latest chunk only'}]], [])
    )
    bot_message = SimpleNamespace(
        resp_message_id='response-1',
        msg_sequence=2,
        all_content='first chunk\n\nlatest chunk only',
        tool_calls=None,
    )
    source = SimpleNamespace(source_platform_object=None)
    message = platform_message.MessageChain([platform_message.Plain(text='latest chunk only')])

    await adapter.reply_message_chunk(source, bot_message, message)

    request = adapter.api_client.cardkit.v1.card_element.content.call_args.args[0]
    assert request.request_body.content == 'first chunk\n\nlatest chunk only'
    adapter.message_converter.yiri2target.assert_not_awaited()


@pytest.mark.asyncio
async def test_lark_streaming_card_first_real_runner_chunk_uses_sequence_one():
    adapter = make_adapter()
    adapter.card_id_dict['response-1'] = 'stream-card-1'
    adapter.card_sequence_dict['stream-card-1'] = 0
    adapter.message_converter.yiri2target = AsyncMock(return_value=([[{'tag': 'text', 'text': 'answer'}]], []))
    bot_message = SimpleNamespace(resp_message_id='response-1', msg_sequence=1, tool_calls=None)
    source = SimpleNamespace(source_platform_object=None)
    message = platform_message.MessageChain([platform_message.Plain(text='answer')])

    await adapter.reply_message_chunk(source, bot_message, message, is_final=True)

    request = adapter.api_client.cardkit.v1.card_element.content.call_args.args[0]
    assert request.request_body.sequence == 1


@pytest.mark.asyncio
async def test_lark_streaming_card_falls_back_to_full_card_update_when_stream_closes():
    adapter = make_adapter()
    adapter.card_id_dict['response-1'] = 'stream-card-1'
    adapter.card_sequence_dict['stream-card-1'] = 1
    adapter.card_last_update_dict['stream-card-1'] = time.monotonic() - 2
    closed_response = DummyResponse(ok=False)
    closed_response.code = 300309
    closed_response.msg = 'streaming mode is closed'
    adapter.api_client.cardkit.v1.card_element.content.return_value = closed_response
    adapter.message_converter.yiri2target = AsyncMock(
        return_value=([[{'tag': 'text', 'text': 'continued progress'}]], [])
    )
    bot_message = SimpleNamespace(resp_message_id='response-1', msg_sequence=2, tool_calls=None)
    source = SimpleNamespace(source_platform_object=None)
    message = platform_message.MessageChain([platform_message.Plain(text='continued progress')])

    await adapter.reply_message_chunk(source, bot_message, message)

    update_request = adapter.api_client.cardkit.v1.card.aupdate.await_args.args[0]
    updated_card = json.loads(update_request.request_body.card.data)
    assert update_request.request_body.sequence == 3
    assert updated_card['config'] == {'update_multi': True}
    assert updated_card['body']['elements'][0]['content'] == 'continued progress'
    assert 'stream-card-1' in adapter.closed_streaming_cards

    bot_message.msg_sequence = 3
    adapter.card_last_update_dict['stream-card-1'] = time.monotonic() - 2
    await adapter.reply_message_chunk(source, bot_message, message, is_final=True)

    assert adapter.api_client.cardkit.v1.card_element.content.call_count == 1
    assert adapter.api_client.cardkit.v1.card.aupdate.await_count == 2
    assert 'stream-card-1' not in adapter.closed_streaming_cards


def test_lark_interaction_callback_builds_scoped_host_event():
    callback = SimpleNamespace(
        event=SimpleNamespace(
            action=SimpleNamespace(value={'lbi': 'callback-token', 't': 'group', 'a': 1}),
            operator=SimpleNamespace(open_id='user-1'),
            context=SimpleNamespace(open_chat_id='chat-1', open_message_id='card-message-1'),
        )
    )

    event = interaction_event_from_callback(callback)

    assert event.action == 'interaction.submitted'
    assert event.data['callback_token'] == 'callback-token'
    assert event.data['action_ref'] == 1
    assert event.data['actor_id'] == 'user-1'
    assert event.data['target_id'] == 'chat-1'
    assert event.data['message_id'] == 'card-message-1'


def test_lark_native_form_callback_submits_typed_field_value():
    callback = SimpleNamespace(
        event=SimpleNamespace(
            action=SimpleNamespace(
                value={
                    'lbi': 'callback-token',
                    't': 'person',
                    'fm': {'lbi_field_0': 'score'},
                    'ft': {'score': 'number'},
                },
                form_value={'lbi_field_0': '42.5'},
            ),
            operator=SimpleNamespace(open_id='user-1'),
            context=SimpleNamespace(open_chat_id='chat-1'),
        )
    )

    event = interaction_event_from_callback(callback)

    assert event.data['callback_token'] == 'callback-token'
    assert event.data['target_type'] == 'person'
    assert event.data['target_id'] == 'user-1'
    assert event.data['values'] == {'score': 42.5}


@pytest.mark.asyncio
async def test_lark_webhook_dispatches_native_form_submission():
    adapter = make_adapter({'enable-webhook': True})
    calls: list[platform_events.Event] = []

    async def listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.PlatformSpecificEvent, listener)
    payload = {
        'schema': '2.0',
        'header': {'event_type': 'card.action.trigger'},
        'event': {
            'action': {
                'value': {
                    'lbi': 'callback-token',
                    't': 'group',
                    'fm': {'lbi_field_0': 'comment'},
                    'ft': {'comment': 'textarea'},
                },
                'form_value': {'lbi_field_0': 'Looks good'},
            },
            'operator': {'open_id': 'user-1'},
            'context': {'open_chat_id': 'chat-1', 'open_message_id': 'card-message-1'},
        },
    }
    request = SimpleNamespace(json=asyncio.sleep(0, result=payload))

    response = await adapter.handle_unified_webhook('bot-1', '', request)

    assert response['toast'] == {'type': 'success', 'content': 'Submitted / 已提交'}
    assert response['card']['type'] == 'raw'
    assert response['card']['data']['elements'][0]['text']['content'] == '**Submitted / 已提交**'
    assert len(calls) == 1
    assert calls[0].action == 'interaction.submitted'
    assert calls[0].data['callback_token'] == 'callback-token'
    assert calls[0].data['values'] == {'comment': 'Looks good'}
    assert calls[0].data['message_id'] == 'card-message-1'


@pytest.mark.asyncio
async def test_lark_webhook_cardkit_submission_uses_async_card_update_only():
    adapter = make_adapter({'enable-webhook': True})

    async def listener(event, adapter):
        pass

    adapter.register_listener(platform_events.PlatformSpecificEvent, listener)
    payload = {
        'schema': '2.0',
        'header': {'event_type': 'card.action.trigger'},
        'event': {
            'action': {'value': {'lbi': 'callback-token', 't': 'group', 'ck': 1, 'a': 0}},
            'operator': {'open_id': 'user-1'},
            'context': {'open_chat_id': 'chat-1', 'open_message_id': 'card-message-1'},
        },
    }
    request = SimpleNamespace(json=asyncio.sleep(0, result=payload))

    response = await adapter.handle_unified_webhook('bot-1', '', request)

    assert response == {'toast': {'type': 'success', 'content': 'Submitted / 已提交'}}
