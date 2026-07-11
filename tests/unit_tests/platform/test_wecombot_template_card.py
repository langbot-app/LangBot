import sys
import types

import pytest


logger_module = types.ModuleType('langbot.pkg.platform.logger')
logger_module.EventLogger = object
sys.modules.setdefault('langbot.pkg.platform.logger', logger_module)

from langbot.libs.wecom_ai_bot_api.api import (  # noqa: E402
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
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient  # noqa: E402


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


def test_text_input_card_shows_direct_reply_prompt():
    payload = build_human_input_template_card_payload(
        {
            'node_title': '人工介入',
            'form_content': '请输入你的问题\n\n{{#$output.us_input#}}',
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
    assert card['main_title']['desc'] == '请直接回复：请输入你的问题'
    assert '请直接回复：请输入你的问题' in card['sub_title_text']
    assert card['button_list'] == []


def test_build_human_input_text_prompt_for_current_text_field():
    prompt = build_human_input_text_prompt(
        {
            'node_title': '人工介入',
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

    assert prompt == '人工介入\n\n请直接回复：请输入你的问题'


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
    assert sent == [('req-1', '人工介入\n\n请直接回复：请输入你的问题')]
    assert client._pending_forms_by_task == {}
    assert 'msg-1' not in client._stream_ids


@pytest.mark.asyncio
async def test_ws_stream_sends_delta_chunks_to_wecom():
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
    assert await client.push_stream_chunk('msg-1', '你好', is_final=True)

    assert sent == [
        ('req-1', 'stream-1', '你', False),
        ('req-1', 'stream-1', '好', False),
        ('req-1', 'stream-1', '', True),
    ]


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


def test_build_multiple_interaction_update_card_disables_submitted_select():
    card = build_multiple_interaction_update_card(
        {
            'node_title': 'Manual Review',
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
        },
        task_id='task-1',
        selections={'choice': 'B'},
    )

    assert card['card_type'] == 'multiple_interaction'
    assert card['main_title']['desc'] == 'Submitted'
    assert card['select_list'][0]['disable'] is True
    assert card['select_list'][0]['selected_id'] == 'opt_2'
