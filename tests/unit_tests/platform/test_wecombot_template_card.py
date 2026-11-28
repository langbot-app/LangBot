import time
import types
from unittest.mock import AsyncMock, Mock

import pytest


from langbot.libs.wecom_ai_bot_api.api import (  # noqa: E402
    WecomBotClient,
    build_button_interaction_payload,
    build_human_input_template_card_payload,
    build_button_interaction_update_card,
    build_multiple_interaction_update_card,
    extract_template_card_event_payload,
    extract_template_card_selections,
    extract_wecom_event_type,
    extract_template_card_action,
    build_human_input_text_prompt,
    parse_select_button_action,
)
from langbot.libs.wecom_ai_bot_api import ws_client  # noqa: E402
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient  # noqa: E402


def test_ws_callback_tasks_are_bounded():
    client = WecomBotWsClient('bot-id', 'secret', object())
    client._callback_tasks = {Mock(done=Mock(return_value=False)) for _ in range(100)}

    async def callback():
        raise AssertionError('rejected callback must not run')

    assert client._start_callback_task(callback()) is False
    assert len(client._callback_tasks) == 100


def test_webhook_dispatch_tasks_are_bounded():
    client = WecomBotClient('', '', '', object(), unified_mode=True)
    client._dispatch_tasks = {Mock(done=Mock(return_value=False)) for _ in range(100)}

    assert client._start_dispatch_task(Mock()) is False
    assert len(client._dispatch_tasks) == 100


@pytest.mark.asyncio
async def test_ws_message_waits_for_real_content_before_creating_stream(monkeypatch):
    from langbot.libs.wecom_ai_bot_api import ws_client as ws_client_module

    order = []
    logger = types.SimpleNamespace(
        debug=Mock(),
        error=Mock(),
        warning=Mock(),
    )
    client = WecomBotWsClient('bot-id', 'secret', logger)

    async def parse_message(*args, **kwargs):
        del args, kwargs
        return {'msgid': 'msg-1', 'type': 'single', 'userid': 'user-1'}

    async def reply_stream(*args, **kwargs):
        raise AssertionError('An empty stream must not be created')

    async def dispatch_event(event):
        del event
        order.append('pipeline-dispatch')

    monkeypatch.setattr(ws_client_module, 'parse_wecom_bot_message', parse_message)
    monkeypatch.setattr(ws_client_module.wecombotevent, 'WecomBotEvent', lambda data: data)
    client.reply_stream = reply_stream
    client._dispatch_event = dispatch_event

    await client._handle_message_callback({'headers': {'req_id': 'req-1'}, 'body': {}})

    assert order == ['pipeline-dispatch']
    assert client._stream_sessions['msg-1']['stream_started'] is False


@pytest.mark.asyncio
async def test_ws_interaction_releases_unused_stream_without_visible_message():
    client = WecomBotWsClient('bot-id', 'secret', object())
    client._stream_ids['msg-1'] = 'req-1|stream-1'
    client._stream_sessions['msg-1'] = {'user_id': 'user-1'}
    sent = []

    async def reply_stream(req_id, stream_id, content, finish=False):
        sent.append((req_id, stream_id, content, finish))
        return {'errcode': 0}

    client.reply_stream = reply_stream
    assert await client.finish_stream_for_interaction('msg-1')
    assert sent == []
    assert 'msg-1' not in client._stream_ids
    assert 'msg-1' not in client._stream_sessions


@pytest.mark.asyncio
async def test_ws_interaction_starts_a_new_stream_after_card():
    client = WecomBotWsClient('bot-id', 'secret', types.SimpleNamespace(info=AsyncMock()))
    client._stream_ids['msg-1'] = 'req-1|old-stream'
    client._stream_sessions['msg-1'] = {
        'req_id': 'req-1',
        'user_id': 'user-1',
        'chat_id': '',
        'created_at': time.monotonic(),
        'stream_started': False,
    }
    sent = []

    async def reply_stream(req_id, stream_id, content, finish=False, feedback_id=''):
        sent.append((req_id, stream_id, content, finish))
        return {'errcode': 0}

    client.reply_stream = reply_stream
    assert await client.finish_stream_for_interaction('msg-1')
    assert sent == []
    assert client.begin_interaction_stream('msg-1', 'person', 'user-1')
    assert not client.begin_interaction_stream('msg-1', 'person', 'user-1')
    assert await client.push_interaction_stream_chunk('msg-1', 'part', False)
    assert await client.push_interaction_stream_chunk('msg-1', 'part done', True)
    assert [item[2:] for item in sent] == [('part', False), ('part done', True)]
    assert sent[0][0] == sent[1][0] == 'req-1'
    assert sent[0][1] == sent[1][1]
    assert sent[0][1] != 'old-stream'


def test_ws_interaction_stream_checks_target_and_expiry():
    client = WecomBotWsClient('bot-id', 'secret', object())
    client._interaction_stream_origins['msg-1'] = {
        'req_id': 'req-1',
        'user_id': 'user-1',
        'chat_id': 'group-1',
        'created_at': time.monotonic(),
    }
    assert not client.begin_interaction_stream('msg-1', 'person', 'other-user')
    assert not client.begin_interaction_stream('msg-1', 'group', 'other-group')
    client._interaction_stream_origins['msg-1']['created_at'] -= 571
    assert not client.begin_interaction_stream('msg-1', 'person', 'user-1')
    assert 'msg-1' not in client._interaction_stream_origins


@pytest.mark.asyncio
async def test_ws_interaction_preserves_existing_stream_text_when_finishing():
    client = WecomBotWsClient('bot-id', 'secret', object())
    client._stream_ids['msg-1'] = 'req-1|stream-1'
    client._stream_sessions['msg-1'] = {'stream_started': True}
    client._stream_last_content['msg-1'] = 'Earlier answer'
    sent = []

    async def reply_stream(req_id, stream_id, content, finish=False):
        sent.append((content, finish))
        return {'errcode': 0}

    client.reply_stream = reply_stream
    assert await client.finish_stream_for_interaction('msg-1')
    assert sent == [('Earlier answer', True)]


@pytest.mark.asyncio
async def test_ws_interaction_finish_failure_keeps_stream_state():
    logger = types.SimpleNamespace(warning=AsyncMock())
    client = WecomBotWsClient('bot-id', 'secret', logger)
    client._stream_ids['msg-1'] = 'req-1|stream-1'
    client._stream_sessions['msg-1'] = {'stream_started': True}

    async def reject(*args, **kwargs):
        raise ConnectionError('disconnected')

    client.reply_stream = reject
    assert not await client.finish_stream_for_interaction('msg-1')
    assert client._stream_ids['msg-1'] == 'req-1|stream-1'


@pytest.mark.asyncio
async def test_ws_rejected_stream_refresh_does_not_complete_session():
    logger = types.SimpleNamespace(error=Mock())
    client = WecomBotWsClient('bot-id', 'secret', logger)
    client._stream_ids['msg-1'] = 'req-1|stream-1'
    client._stream_sessions['msg-1'] = {'user_id': 'user-1'}

    async def reject(*args, **kwargs):
        return {'errcode': 400, 'errmsg': 'invalid req_id'}

    async def record_error(message):
        assert 'invalid req_id' in message

    client.reply_stream = reject
    logger.error = record_error
    assert not await client.push_stream_chunk('msg-1', 'answer', is_final=True)
    assert 'msg-1' in client._stream_ids


@pytest.mark.asyncio
async def test_ws_stream_starts_with_first_real_content(monkeypatch):
    from langbot.libs.wecom_ai_bot_api import ws_client as ws_client_module

    dispatched = []

    class Logger:
        def __init__(self):
            self.warnings = []

        async def debug(self, message):
            del message

        async def error(self, message):
            raise AssertionError(message)

        async def warning(self, message):
            self.warnings.append(message)

    logger = Logger()
    client = WecomBotWsClient('bot-id', 'secret', logger)

    async def parse_message(*args, **kwargs):
        del args, kwargs
        return {'msgid': 'msg-1', 'type': 'single', 'userid': 'user-1'}

    sent = []

    async def reply_stream(req_id, stream_id, content, finish=False, feedback_id=''):
        sent.append((req_id, content, finish))
        return {'errcode': 0}

    async def dispatch_event(event):
        dispatched.append(event)

    monkeypatch.setattr(ws_client_module, 'parse_wecom_bot_message', parse_message)
    monkeypatch.setattr(ws_client_module.wecombotevent, 'WecomBotEvent', lambda data: data)
    client.reply_stream = reply_stream
    client._dispatch_event = dispatch_event

    await client._handle_message_callback({'headers': {'req_id': 'req-1'}, 'body': {}})
    assert sent == []
    assert await client.push_stream_chunk('msg-1', 'hello')

    assert len(dispatched) == 1
    assert sent == [('req-1', 'hello', False)]
    assert client._stream_sessions['msg-1']['stream_started'] is True
    assert logger.warnings == []

    assert await client.push_stream_chunk('msg-1', 'hello', is_final=True)
    assert 'msg-1' not in client._stream_ids
    assert client.begin_interaction_stream('msg-1', 'person', 'user-1')


def test_extract_template_card_action_supports_nested_button_key():
    task_id, event_key, card_type = extract_template_card_action(
        {
            'taskId': 'task-1',
            'cardType': 'button_interaction',
            'button': {'key': 'approve'},
        }
    )

    assert task_id == 'task-1'
    assert event_key == 'approve'
    assert card_type == 'button_interaction'


def test_extract_wecom_event_type_supports_top_level_template_card_event():
    payload = {
        'eventtype': 'template_card_event',
        'template_card_event': {
            'TaskId': 'task-1',
            'CardType': 'multiple_interaction',
            'ResponseData': '{"select_list":[{"question_key":"choice","option_id":"opt_2"}]}',
        },
    }

    assert extract_wecom_event_type(payload) == 'template_card_event'
    assert extract_template_card_event_payload(payload)['TaskId'] == 'task-1'


def test_extract_wecom_event_type_infers_template_card_event_from_top_level_card_fields():
    payload = {
        'TaskId': 'task-1',
        'CardType': 'button_interaction',
        'EventKey': 'approve',
    }

    assert extract_wecom_event_type(payload) == 'template_card_event'
    assert extract_template_card_event_payload(payload)['EventKey'] == 'approve'


def test_build_button_interaction_update_card_marks_clicked_button():
    card = build_button_interaction_update_card(
        {
            'node_title': 'Manual Review',
            'form_content': 'Please choose one action.',
            'actions': [
                {'id': 'approve', 'title': 'Approve', 'button_style': 'primary'},
                {'id': 'reject', 'title': 'Reject', 'button_style': 'danger'},
            ],
        },
        task_id='task-1',
        action_id='reject',
        source={'desc': 'LangBot'},
    )

    assert card['main_title'] == {'title': 'Manual Review'}
    assert card['sub_title_text'] == 'Please choose one action.'
    assert card['button_list'][0] == {'text': 'Approve', 'style': 2, 'key': 'approve'}
    assert card['button_list'][1] == {
        'text': '✅ Reject',
        'style': 1,
        'key': 'reject',
        'replace_text': '✅ Reject',
    }
    assert card['source'] == {'desc': 'LangBot'}


def test_build_button_interaction_payload_uses_preselected_button_styles_before_click():
    payload = build_button_interaction_payload(
        {
            'node_title': 'Manual Review',
            'actions': [
                {'id': 'approve', 'title': 'Approve', 'button_style': 'primary'},
                {'id': 'reject', 'title': 'Reject', 'button_style': 'danger'},
            ],
        },
        task_id='task-1',
    )

    assert payload['template_card']['button_list'] == [
        {'text': 'Approve', 'style': 2, 'key': 'approve'},
        {'text': 'Reject', 'style': 2, 'key': 'reject'},
    ]


def test_build_payload_uses_multiple_interaction_for_pending_select_field():
    payload = build_human_input_template_card_payload(
        {
            'node_title': 'Manual Review',
            'form_content': 'Choose a label\n\n{{#$output.choice#}}',
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
            'inputs': {},
            'actions': [{'id': 'yes', 'title': 'Yes'}],
        },
        task_id='task-1',
        source={'desc': 'LangBot'},
    )

    card = payload['template_card']
    assert card['card_type'] == 'multiple_interaction'
    assert card['source'] == {'desc': 'LangBot'}
    assert card['select_list'] == [
        {
            'question_key': 'choice',
            'title': 'choice',
            'selected_id': 'opt_1',
            'option_list': [
                {'id': 'opt_1', 'text': 'A'},
                {'id': 'opt_2', 'text': 'B'},
            ],
        }
    ]
    assert card['submit_button'] == {'text': 'Submit', 'key': 'submit_human_input'}


def test_build_payload_can_emulate_select_as_buttons_for_wecombot_ws():
    form_data = {
        'node_title': 'Manual Review',
        'form_content': 'Choose a label\n\n{{#$output.choice#}}',
        'input_defs': [
            {
                'output_variable_name': 'choice',
                'type': 'select',
                'option_source': {'type': 'constant', 'value': ['A', 'B']},
            }
        ],
        'inputs': {},
        'actions': [{'id': 'yes', 'title': 'Yes'}],
    }
    payload = build_human_input_template_card_payload(
        form_data,
        task_id='task-1',
        select_as_buttons=True,
    )

    card = payload['template_card']
    assert card['card_type'] == 'button_interaction'
    assert card['button_list'][0]['text'] == 'A'
    assert parse_select_button_action(card['button_list'][1]['key'], form_data) == {'choice': 'B'}


def test_text_input_card_uses_current_stage_content_without_direct_reply_prompt():
    payload = build_human_input_template_card_payload(
        {
            'node_title': '人工介入',
            'form_content': '11\n请输入你的问题\n\n{{#$output.us_input#}}',
            'raw_form_content': ('11\n请输入你的问题\n{{#$output.us_input#}}\n请选择你的答案\n{{#$output.xiala#}}'),
            'input_defs': [
                {
                    'output_variable_name': 'us_input',
                    'type': 'paragraph',
                    'label': '请输入你的问题',
                }
            ],
            'inputs': {},
            'actions': [{'id': 'yes', 'title': 'yes'}],
            '_current_input_field': 'us_input',
        },
        task_id='task-1',
    )

    card = payload['template_card']
    assert 'desc' not in card['main_title']
    assert card['sub_title_text'] == '11\n请输入你的问题'
    assert card['button_list'] == []


def test_build_human_input_text_prompt_for_current_text_field():
    prompt = build_human_input_text_prompt(
        {
            'node_title': '人工介入',
            'form_content': '11\n请输入你的问题\n{{#$output.us_input#}}',
            'raw_form_content': ('11\n请输入你的问题\n{{#$output.us_input#}}\n请选择你的答案\n{{#$output.xiala#}}'),
            'input_defs': [
                {
                    'output_variable_name': 'us_input',
                    'type': 'paragraph',
                    'label': '请输入你的问题',
                }
            ],
            '_current_input_field': 'us_input',
        }
    )

    assert prompt == '人工介入\n\n11\n请输入你的问题'


@pytest.mark.asyncio
async def test_ws_push_form_pause_sends_text_prompt_without_empty_card():
    client = WecomBotWsClient('bot-id', 'secret', object())
    client._stream_ids['msg-1'] = 'req-1|stream-1'
    client._stream_sessions['msg-1'] = {'user_id': 'user-1'}
    sent = []

    async def fake_reply_text(req_id, content):
        sent.append((req_id, content))
        return {}

    client.reply_text = fake_reply_text

    ok, stream_id, task_id = await client.push_form_pause(
        'msg-1',
        {
            'node_title': '人工介入',
            'form_content': '11\n请输入你的问题\n{{#$output.us_input#}}',
            'raw_form_content': ('11\n请输入你的问题\n{{#$output.us_input#}}\n请选择你的答案\n{{#$output.xiala#}}'),
            'input_defs': [
                {
                    'output_variable_name': 'us_input',
                    'type': 'paragraph',
                    'label': '请输入你的问题',
                }
            ],
            '_current_input_field': 'us_input',
        },
    )

    assert ok is True
    assert stream_id == 'stream-1'
    assert task_id is None
    assert sent == [('req-1', '人工介入\n\n11\n请输入你的问题')]
    assert client._pending_forms_by_task == {}
    assert 'msg-1' not in client._stream_ids


@pytest.mark.asyncio
async def test_ws_stream_sends_cumulative_snapshots_to_wecom(monkeypatch):
    # Frame pacing has its own coverage in test_wecombot_stream_throttle.py.
    # Disable it here so this test keeps asserting what it is named for: that
    # every frame carries the cumulative snapshot rather than a delta.
    monkeypatch.setattr(ws_client, '_STREAM_PUSH_MIN_INTERVAL', 0.0)

    client = WecomBotWsClient('bot-id', 'secret', object())
    client._stream_ids['msg-1'] = 'req-1|stream-1'
    client._stream_sessions['msg-1'] = {}
    sent = []

    async def fake_reply_stream(req_id, stream_id, content, finish=False, feedback_id=''):
        sent.append((req_id, stream_id, content, finish))
        return {}

    client.reply_stream = fake_reply_stream

    assert await client.push_stream_chunk('msg-1', '你', is_final=False)
    assert await client.push_stream_chunk('msg-1', '你好', is_final=False)
    assert await client.push_stream_chunk('msg-1', '<think>test</think>你好', is_final=False)
    assert await client.push_stream_chunk('msg-1', '你好', is_final=True)

    assert sent == [
        ('req-1', 'stream-1', '你', False),
        ('req-1', 'stream-1', '你好', False),
        ('req-1', 'stream-1', '<think>test</think>你好', False),
        ('req-1', 'stream-1', '你好', True),
    ]


@pytest.mark.asyncio
async def test_webhook_stream_queues_cumulative_snapshots_for_followups():
    client = WecomBotClient('', '', '', object(), unified_mode=True)
    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-1', 'chatid': '', 'from': {'userid': 'user-1'}})

    assert await client.push_stream_chunk('msg-1', '你', is_final=False)
    assert await client.push_stream_chunk('msg-1', '你好', is_final=False)
    assert await client.push_stream_chunk('msg-1', '<think>test</think>你好', is_final=False)
    assert await client.push_stream_chunk('msg-1', '你好', is_final=True)

    assert session.queue.qsize() == 1
    chunk = await client.stream_sessions.consume(session.stream_id)
    assert (chunk.content, chunk.is_final) == ('你好', True)


def test_human_input_payload_keeps_action_select_stage_as_buttons():
    payload = build_human_input_template_card_payload(
        {
            'node_title': 'Manual Review',
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
            'inputs': {'choice': 'B'},
            'actions': [
                {'id': 'approve', 'title': 'Approve'},
                {'id': 'reject', 'title': 'Reject'},
            ],
            '_action_select_only': True,
        },
        task_id='task-1',
    )

    card = payload['template_card']
    assert card['card_type'] == 'button_interaction'
    assert card['button_list'] == [
        {'text': 'Approve', 'style': 2, 'key': 'approve'},
        {'text': 'Reject', 'style': 2, 'key': 'reject'},
    ]


def test_extract_template_card_selections_maps_selected_id_to_option_text():
    selections = extract_template_card_selections(
        {
            'SelectedItems': [
                {'QuestionKey': 'choice', 'SelectedId': 'opt_2'},
            ],
        },
        {
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
        },
    )

    assert selections == {'choice': 'B'}


def test_extract_template_card_selections_reads_nested_response_data_json():
    selections = extract_template_card_selections(
        {
            'CardType': 'multiple_interaction',
            'ResponseData': '{"select_list":[{"question_key":"choice","option_id":"opt_2"}]}',
        },
        {
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
        },
    )

    assert selections == {'choice': 'B'}


def test_extract_template_card_selections_reads_response_data_direct_mapping():
    selections = extract_template_card_selections(
        {
            'CardType': 'multiple_interaction',
            'EventKey': 'submit_human_input',
            'ResponseData': '{"choice":"opt_2"}',
        },
        {
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
        },
    )

    assert selections == {'choice': 'B'}


def test_build_multiple_interaction_update_card_disables_selected_value_without_submitted_text():
    card = build_multiple_interaction_update_card(
        {
            'node_title': 'Manual Review',
            'form_content': 'Choose a label\n{{#$output.choice#}}',
            'raw_form_content': 'Choose a label\n{{#$output.choice#}}',
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
            '_current_input_field': 'choice',
        },
        task_id='task-1',
        selections={'choice': 'B'},
    )

    assert card['card_type'] == 'multiple_interaction'
    assert card['main_title']['desc'] == 'Choose a label\n✅ choice：B'
    assert card['submit_button']['text'] == '✅'
    assert card['select_list'][0]['disable'] is True
    assert card['select_list'][0]['selected_id'] == 'opt_2'


def test_select_stage_only_shows_current_prompt_in_a_separate_message():
    raw_content = '11\n请输入你的问题\n{{#$output.us_input#}}\n请选择你的答案\n{{#$output.xiala#}}'
    payload = build_human_input_template_card_payload(
        {
            'node_title': '人工介入',
            'form_content': '请选择你的答案\n{{#$output.xiala#}}',
            'raw_form_content': raw_content,
            'input_defs': [
                {
                    'output_variable_name': 'xiala',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['1', '2']},
                }
            ],
            'all_input_defs': [
                {'output_variable_name': 'us_input', 'type': 'paragraph'},
                {
                    'output_variable_name': 'xiala',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['1', '2']},
                },
            ],
            'inputs': {'us_input': '你叫啥'},
            '_current_input_field': 'xiala',
        },
        task_id='task-1',
    )

    assert payload['template_card']['main_title']['desc'] == '请选择你的答案'


def test_action_stage_only_shows_content_after_fields_without_placeholders():
    raw_content = '11\n请输入你的问题\n{{#$output.us_input#}}\n请选择你的答案\n{{#$output.xiala#}}\n请选择操作'
    payload = build_human_input_template_card_payload(
        {
            'node_title': '人工介入',
            'form_content': raw_content,
            'raw_form_content': raw_content,
            'input_defs': [],
            'all_input_defs': [
                {'output_variable_name': 'us_input', 'type': 'paragraph'},
                {'output_variable_name': 'xiala', 'type': 'select'},
            ],
            'inputs': {'us_input': '你叫啥', 'xiala': '2'},
            'actions': [
                {'id': 'yes', 'title': 'yes'},
                {'id': 'no', 'title': 'no'},
            ],
            '_action_select_only': True,
        },
        task_id='task-1',
    )

    card = payload['template_card']
    assert card['sub_title_text'] == '请选择操作'
    assert '{{#$output.' not in card['sub_title_text']
    assert [button['text'] for button in card['button_list']] == ['yes', 'no']


@pytest.mark.asyncio
async def test_webhook_enter_chat_returns_welcome_without_message_stream():
    from unittest.mock import AsyncMock
    from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent

    logger = types.SimpleNamespace(info=AsyncMock(), debug=AsyncMock(), error=AsyncMock(), warning=AsyncMock())
    client = WecomBotClient('', '', '', logger, unified_mode=True)
    client._encrypt_and_reply = AsyncMock(side_effect=lambda reply, nonce: reply)
    ordinary = AsyncMock()
    client.on_message('single')(ordinary)

    async def welcome(event):
        assert isinstance(event, WecomBotEvent)
        await client.reply_welcome(event.message_id, 'Welcome')

    client.on_message('event')(welcome)
    result = await client._handle_enter_chat(
        {
            'msgid': 'entry-1',
            'msgtype': 'event',
            'chattype': 'single',
            'from': {'userid': 'visitor'},
            'event': {'eventtype': 'enter_chat'},
        },
        'nonce',
    )
    assert result == {'msgtype': 'text', 'text': {'content': 'Welcome'}}
    ordinary.assert_not_awaited()
    assert not client._welcome_replies
    with pytest.raises(ValueError, match='expired'):
        await client.reply_welcome('entry-1', 'too late')
    await client.close()


@pytest.mark.asyncio
async def test_webhook_unmanaged_card_dispatches_but_expired_dify_does_not():
    import asyncio
    from unittest.mock import AsyncMock

    logger = types.SimpleNamespace(info=AsyncMock(), debug=AsyncMock(), error=AsyncMock(), warning=AsyncMock())
    client = WecomBotClient('', '', '', logger, unified_mode=True)
    client._encrypt_and_reply = AsyncMock(return_value={})
    handler = AsyncMock()
    client.on_message('template_card_event')(handler)
    for task_id in ['business-card', 'dify-expired']:
        await client._handle_template_card_event(
            {
                'msgid': task_id,
                'msgtype': 'event',
                'chattype': 'single',
                'from': {'userid': 'visitor'},
                'event': {
                    'eventtype': 'template_card_event',
                    'template_card_event': {
                        'task_id': task_id,
                        'event_key': 'approve',
                    },
                },
            },
            'nonce',
        )
    await asyncio.gather(*client._dispatch_tasks)
    handler.assert_awaited_once()
    assert handler.await_args.args[0].userid == 'visitor'
    await client.close()


@pytest.mark.asyncio
async def test_ws_welcome_uses_dedicated_command():
    from unittest.mock import AsyncMock

    client = WecomBotWsClient('bot-id', 'secret', object())
    client._send_reply = AsyncMock(return_value={})
    await client.reply_welcome('req-1', 'Welcome')
    client._send_reply.assert_awaited_once_with(
        'req-1', {'msgtype': 'text', 'text': {'content': 'Welcome'}}, cmd='aibot_respond_welcome_msg'
    )


@pytest.mark.asyncio
async def test_expired_custom_managed_card_never_becomes_business_event():
    from unittest.mock import AsyncMock

    logger = types.SimpleNamespace(info=AsyncMock(), debug=AsyncMock(), error=AsyncMock(), warning=AsyncMock())
    client = WecomBotWsClient('bot-id', 'secret', logger)
    handler = AsyncMock()
    client.on_message('template_card_event')(handler)
    client._drop_pending_form_task('custom-managed-task', {})
    body = {
        'msgtype': 'event',
        'event': {
            'eventtype': 'template_card_event',
            'template_card_event': {
                'task_id': 'custom-managed-task',
                'event_key': 'approve',
            },
        },
    }
    await client._handle_template_card_event_frame({'headers': {'req_id': 'r1'}}, body)
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_welcome_timeout_cleans_pending_reply(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    logger = types.SimpleNamespace(info=AsyncMock(), debug=AsyncMock(), error=AsyncMock(), warning=AsyncMock())
    client = WecomBotClient('', '', '', logger, unified_mode=True)
    client._encrypt_and_reply = AsyncMock(side_effect=lambda reply, nonce: reply)

    async def timeout(awaitable, timeout):
        awaitable.cancel()
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, 'wait_for', timeout)
    result = await client._handle_enter_chat(
        {
            'msgid': 'no-reply',
            'msgtype': 'event',
            'event': {'eventtype': 'enter_chat'},
        },
        'nonce',
    )
    assert result == {}
    assert not client._welcome_replies
    await client.close()
