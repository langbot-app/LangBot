from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml

from langbot.libs.dingtalk_api.api import DingTalkClient
from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
from langbot.pkg.agent.runner.interaction_manager import InteractionManager
from langbot.pkg.platform.adapters.dingtalk.adapter import DingTalkAdapter, DingTalkCardCallbackHandler
from langbot.pkg.platform.adapters.dingtalk.event_converter import DingTalkEventConverter
from langbot.pkg.platform.adapters.dingtalk.message_converter import DingTalkMessageConverter
from langbot.pkg.platform.adapters.dingtalk.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.dingtalk.interaction import interaction_event_from_native
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
        self.client = SimpleNamespace(register_callback_handler=Mock(), register_all_event_handler=Mock())
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
        self.create_and_deliver_ai_card = AsyncMock(return_value={})
        self.update_ai_card = AsyncMock(return_value={})
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
    return yaml.safe_load(manifest_path.read_text(encoding='utf-8'))


def make_adapter() -> DingTalkAdapter:
    config = {
        'client_id': 'client-id',
        'client_secret': 'client-secret',
        'robot_name': 'LangBot',
        'robot_code': 'robot-code',
        'markdown_card': True,
        'enable-stream-reply': False,
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


def dingtalk_card_callback_event(**overrides) -> DingTalkEvent:
    return DingTalkEvent.from_payload(
        {
            'conversation_type': 'CardCallback',
            'Type': 'card_callback',
            'CardCallback': {
                'extension': overrides.get('extension', {}),
                'corp_id': overrides.get('corp_id', 'corp-1'),
                'user_id': overrides.get('user_id', 'user-1'),
                'content': overrides.get(
                    'content',
                    {
                        'action': 'like',
                        'feedback_id': 'feedback-1',
                        'message_id': 'bot-msg-1',
                    },
                ),
                'space_id': overrides.get('space_id', 'space-1'),
                'card_instance_id': overrides.get('card_instance_id', 'card-1'),
            },
        }
    )


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
    assert chain[2].text == '@LangBot hello'
    assert isinstance(chain[3], platform_message.File)
    assert isinstance(chain[4], platform_message.Quote)
    assert str(chain[4].origin) == 'quoted text'


@pytest.mark.asyncio
async def test_dingtalk_event_converter_maps_group_and_private_message():
    group_event = await DingTalkEventConverter.target2yiri(dingtalk_event(), 'LangBot')

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.adapter_name == 'dingtalk-omni'
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
async def test_dingtalk_event_converter_maps_card_feedback():
    feedback = await DingTalkEventConverter.target2yiri(dingtalk_card_callback_event(), 'LangBot')
    callback = await DingTalkEventConverter.target2yiri(
        dingtalk_card_callback_event(content={'action': 'open_details'}),
        'LangBot',
    )

    assert isinstance(feedback, platform_events.FeedbackReceivedEvent)
    assert feedback.adapter_name == 'dingtalk-omni'
    assert feedback.feedback_id == 'feedback-1'
    assert feedback.feedback_type == 1
    assert feedback.user_id == 'user-1'
    assert feedback.session_id == 'space-1'
    assert feedback.message_id == 'bot-msg-1'

    assert isinstance(callback, platform_events.DingTalkCardActionEvent)
    assert callback.action == 'open_details'


@pytest.mark.asyncio
async def test_dingtalk_adapter_dispatches_card_feedback_event():
    adapter = make_adapter()
    calls: list[platform_events.Event] = []

    async def listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.FeedbackReceivedEvent, listener)
    await adapter._handle_native_event(dingtalk_card_callback_event())

    assert len(calls) == 1
    assert isinstance(calls[0], platform_events.FeedbackReceivedEvent)
    assert calls[0].feedback_type == 1


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


@pytest.mark.asyncio
async def test_dingtalk_interaction_delivery_and_callback_event():
    adapter = make_adapter()
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'group', 'target_id': 'group-1'},
            'request': {
                'interaction_id': 'form-1',
                'title': 'Approve?',
                'actions': [{'id': 'approve', 'label': 'Approve', 'style': 'primary'}],
                'fallback_text': 'Reply approve.',
            },
        },
    )

    assert result['rich'] is True
    kwargs = adapter.bot.create_and_deliver_ai_card.await_args.kwargs
    assert kwargs['open_space_id'] == 'dtv1.card//im_group.group-1'
    assert kwargs['flow_status'] == 'CONFIRMING'
    components = kwargs['a2ui_messages'][2]['updateComponents']['components']
    button = next(component for component in components if component['component'] == 'Button')
    assert button['action']['event']['context']['actionId'] == 'lbi:callback-token:a:0'
    assert components[0]['children'][-1] == 'langbot-brand'
    assert any(component['id'] == 'langbot-brand-link' for component in components)

    native = dingtalk_card_callback_event(
        content={'actionId': 'lbi:callback-token:a:0'},
        space_id='dtv1.card//IM_GROUP.group-1',
    )
    event = interaction_event_from_native(native)
    assert event.action == 'interaction.submitted'
    assert event.data['action_ref'] == 0
    assert event.data['actor_id'] == 'user-1'
    assert event.data['target_id'] == 'group-1'


@pytest.mark.asyncio
async def test_dingtalk_native_input_uses_template_variables_and_submits_value():
    adapter = make_adapter()
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'group', 'target_id': 'group-1'},
            'request': {
                'interaction_id': 'form-1',
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
                'fallback_text': 'Reply with a comment.',
            },
        },
    )

    kwargs = adapter.bot.create_and_deliver_ai_card.await_args.kwargs
    components = kwargs['a2ui_messages'][2]['updateComponents']['components']
    field = next(component for component in components if component['component'] == 'TextField')
    button = next(component for component in components if component['component'] == 'Button')
    assert field['label'] == 'Comment'
    assert field['placeholder'] == 'Explain the decision'
    assert field['variant'] == 'longText'
    assert button['checks'] == [
        {
            'condition': {'call': 'required', 'args': {'value': {'path': '/form/comment'}}},
            'message': 'Comment is required',
        }
    ]
    assert result['message_id'] in adapter.interaction_callback_contexts

    native = dingtalk_card_callback_event(
        content={
            'actionData': {
                'a2uiAction': {
                    'context': {
                        'actionId': 'lbi:callback-token:f:0',
                        'values': {'comment': 'Looks good'},
                    }
                }
            }
        },
        card_instance_id=result['message_id'],
        space_id='dtv1.card//im_group.group-1',
    )
    event = interaction_event_from_native(native, adapter.interaction_callback_contexts)

    assert event.data['callback_token'] == 'callback-token'
    assert event.data['values'] == {'comment': 'Looks good'}
    assert result['message_id'] in adapter.interaction_callback_contexts


@pytest.mark.asyncio
async def test_dingtalk_native_select_uses_select_block_and_normalizes_callback():
    adapter = make_adapter()
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'person', 'target_id': 'user-1'},
            'request': {
                'interaction_id': 'form-1',
                'title': 'Priority',
                'fields': [
                    {
                        'id': 'priority',
                        'label': 'Priority',
                        'type': 'select',
                        'options': [
                            {'value': 'normal', 'label': 'Normal'},
                            {'value': 'urgent', 'label': 'Urgent'},
                        ],
                    }
                ],
                'actions': [],
                'fallback_text': 'Choose a priority.',
            },
        },
    )

    kwargs = adapter.bot.create_and_deliver_ai_card.await_args.kwargs
    components = kwargs['a2ui_messages'][2]['updateComponents']['components']
    field = next(component for component in components if component['component'] == 'ChoicePicker')
    assert field['displayStyle'] == 'dropdown'
    assert [option['value'] for option in field['options']] == ['normal', 'urgent']

    native = dingtalk_card_callback_event(
        content={
            'actionData': {
                'a2uiAction': {
                    'context': {
                        'actionId': 'lbi:callback-token:f:0',
                        'values': {'priority': ['urgent']},
                    }
                }
            }
        },
        card_instance_id=result['message_id'],
        space_id='dtv1.card//im_robot.user-1',
    )
    event = interaction_event_from_native(native, adapter.interaction_callback_contexts)

    assert event.data['target_type'] == 'person'
    assert event.data['target_id'] == 'user-1'
    assert event.data['values'] == {'priority': 'urgent'}
    assert 'field_ref' not in event.data
    resolved = InteractionManager._resolve_submission_refs(
        {
            'interaction_id': 'form-1',
            'request': {
                'fields': [
                    {'id': 'priority', 'type': 'select', 'options': [{'value': 'urgent'}]},
                ]
            },
        },
        {'values': event.data['values']},
    )
    assert resolved['values'] == {'priority': 'urgent'}


@pytest.mark.asyncio
async def test_dingtalk_stream_callback_submits_dropdown_without_space_id():
    adapter = make_adapter()
    received = []

    async def listener(event, _adapter):
        received.append(event)

    adapter.register_listener(platform_events.PlatformSpecificEvent, listener)
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'person', 'target_id': 'user-1'},
            'request': {
                'title': 'Priority',
                'fields': [
                    {
                        'id': 'priority',
                        'type': 'select',
                        'options': [{'value': 'urgent', 'label': 'Urgent'}],
                    }
                ],
            },
        },
    )
    raw_callback = {
        'outTrackId': result['message_id'],
        'userId': 'user-1',
        'corpId': 'corp-1',
        'extension': '{}',
        'content': json.dumps(
            {
                'actionData': {
                    'a2uiAction': {
                        'context': {
                            'actionId': 'lbi:callback-token:f:0',
                            'values': {'priority': ['urgent']},
                        }
                    }
                }
            }
        ),
    }

    await DingTalkCardCallbackHandler(adapter).process(
        SimpleNamespace(data=raw_callback, headers=SimpleNamespace(time=1_714_000_000_000))
    )

    assert len(received) == 1
    assert received[0].action == 'interaction.submitted'
    assert received[0].data['target_type'] == 'person'
    assert received[0].data['target_id'] == 'user-1'
    assert received[0].data['values'] == {'priority': 'urgent'}
    assert result['message_id'] in adapter.interaction_callback_contexts


@pytest.mark.asyncio
async def test_dingtalk_stream_callback_accepts_object_content_and_retries_unparsed_action():
    adapter = make_adapter()
    received = []

    async def listener(event, _adapter):
        received.append(event)

    adapter.register_listener(platform_events.PlatformSpecificEvent, listener)
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'person', 'target_id': 'user-1'},
            'request': {'fields': [{'id': 'priority', 'type': 'select', 'options': [{'value': 'urgent'}]}]},
        },
    )
    raw = {
        'outTrackId': result['message_id'],
        'userId': 'user-1',
        'content': {
            'actionData': {
                'a2uiAction': {
                    'context': {
                        'actionId': 'lbi:callback-token:f:0',
                        'values': {'priority': ['urgent']},
                    }
                }
            }
        },
    }
    handler = DingTalkCardCallbackHandler(adapter)
    message = SimpleNamespace(data=raw, headers=SimpleNamespace(time=1_714_000_000_000))

    assert (await handler.process(message))[0] == 200
    assert received[0].data['values'] == {'priority': 'urgent'}
    raw['content'] = {'actionData': {'unexpected': True}}
    assert (await handler.process(message))[0] == 500


@pytest.mark.asyncio
async def test_dingtalk_interaction_update_reuses_existing_a2ui_card():
    adapter = make_adapter()

    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'new-token',
            'reply_target': {'target_type': 'group', 'target_id': 'group-1'},
            'update_target': {'message_id': 'existing-track-id', 'rich': True},
            'request': {
                'interaction_id': 'form-2',
                'title': 'Updated approval',
                'actions': [{'id': 'approve', 'label': 'Approve', 'style': 'primary'}],
                'fallback_text': 'Reply approve.',
            },
        },
    )

    adapter.bot.create_and_deliver_ai_card.assert_not_awaited()
    kwargs = adapter.bot.update_ai_card.await_args.kwargs
    assert kwargs['out_track_id'] == 'existing-track-id'
    assert kwargs['flow_status'] == 'CONFIRMING'
    assert 'updateDataModel' in kwargs['a2ui_messages'][0]
    assert 'updateComponents' in kwargs['a2ui_messages'][1]
    assert result == {
        'ok': True,
        'message_id': 'existing-track-id',
        'rich': True,
        'updated': True,
    }
    assert adapter.interaction_callback_contexts['existing-track-id']['callback_token'] == 'new-token'


def test_dingtalk_stale_callback_does_not_consume_replacement_context():
    contexts = {
        'card-1': {
            'callback_token': 'new-token',
            'field_types': {},
            'expires_at': float('inf'),
        }
    }
    native = dingtalk_card_callback_event(
        content={'actionId': 'lbi:old-token:a:0'},
        card_instance_id='card-1',
        space_id='dtv1.card//im_group.group-1',
    )

    assert interaction_event_from_native(native, contexts) is None
    assert contexts['card-1']['callback_token'] == 'new-token'


@pytest.mark.asyncio
async def test_dingtalk_adapter_dispatches_native_input_submission():
    adapter = make_adapter()
    calls: list[platform_events.Event] = []

    async def listener(event, adapter):
        calls.append(event)

    adapter.register_listener(platform_events.PlatformSpecificEvent, listener)
    result = await adapter.call_platform_api(
        'interaction.request',
        {
            'callback_token': 'callback-token',
            'reply_target': {'target_type': 'group', 'target_id': 'group-1'},
            'request': {
                'interaction_id': 'form-1',
                'title': 'Score',
                'fields': [
                    {
                        'id': 'score',
                        'label': 'Score',
                        'type': 'number',
                    }
                ],
                'actions': [],
                'fallback_text': 'Reply with a score.',
            },
        },
    )
    native = dingtalk_card_callback_event(
        content={
            'actionData': {
                'a2uiAction': {
                    'context': {
                        'actionId': 'lbi:callback-token:f:0',
                        'values': {'score': 42.5},
                    }
                }
            }
        },
        card_instance_id=result['message_id'],
        space_id='dtv1.card//im_group.group-1',
    )

    await adapter._handle_native_event(native)

    assert len(calls) == 1
    assert calls[0].action == 'interaction.submitted'
    assert calls[0].data['callback_token'] == 'callback-token'
    assert calls[0].data['values'] == {'score': 42.5}
    assert result['message_id'] in adapter.interaction_callback_contexts


def test_dingtalk_subscription_member_and_group_mapping():
    from dingtalk_stream.frames import EventMessage
    from langbot.pkg.platform.adapters.dingtalk.subscriptions import subscription_events

    message = EventMessage()
    message.headers.event_type = 'chat_add_member'
    message.data = {'OpenConversationId': 'group', 'UserId': ['a', 'b']}
    converted = list(subscription_events(message))
    assert [event.member.id for event in converted] == ['a', 'b']
    assert all(event.type == 'group.member_joined' for event in converted)
    message.headers.event_type = 'chat_update_owner'
    message.data = {'OpenConversationId': 'group', 'Owner': 'new-owner'}
    event = list(subscription_events(message))[0]
    assert event.changed_fields == ['owner_id']
    assert event.group.owner_id == 'new-owner'
    message.headers.event_type = 'chat_add_member'
    message.data = {'chatId': 'group', 'unionId': ['union-id']}
    assert list(subscription_events(message))[0].type == 'platform.specific'


@pytest.mark.asyncio
async def test_dingtalk_subscription_retry_does_not_repeat_successful_members():
    from dingtalk_stream.frames import EventMessage
    from langbot.pkg.platform.adapters.dingtalk.subscriptions import DingTalkSubscriptionHandler

    message = EventMessage()
    message.headers.event_id = 'event-1'
    message.headers.event_type = 'chat_add_member'
    message.data = {'OpenConversationId': 'group', 'UserId': ['a', 'b']}
    adapter = SimpleNamespace(_dispatch_eba_event=AsyncMock(side_effect=[None, RuntimeError('retry'), None]))
    handler = DingTalkSubscriptionHandler(adapter)
    assert (await handler.process(message))[0] == 500
    assert (await handler.process(message))[0] == 200
    assert (await handler.process(message))[0] == 200
    assert [call.args[0].member.id for call in adapter._dispatch_eba_event.await_args_list] == ['a', 'b', 'b']
