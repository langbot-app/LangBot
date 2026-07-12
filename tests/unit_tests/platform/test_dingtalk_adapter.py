"""Tests for DingTalk adapter helper behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langbot.pkg.platform.sources.dingtalk import (
    DingTalkAdapter,
    _dingtalk_card_markdown,
    _dingtalk_clean_form_content,
    _dingtalk_completed_input_lines,
    _dingtalk_extract_component_inputs,
    _dingtalk_form_component_params,
    _dingtalk_missing_completed_input_lines,
    _dingtalk_pending_input_defs,
)


def test_dingtalk_select_component_params_expose_options():
    params = _dingtalk_form_component_params(
        {
            '_current_input_field': 'choice',
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ],
            'inputs': {},
        }
    )

    assert params['select_visible'] == 'true'
    assert params['select_placeholder'] == 'choice'
    assert params['select_options'] == ['A', 'B']
    assert [option['value'] for option in params['index_o']] == ['A', 'B']
    assert [option['value'] for option in params['test_index']] == ['A', 'B']
    assert params['index_o'][0]['text']['zh_CN'] == 'A'
    assert params['index_o'][0]['text']['en_US'] == 'A'
    assert params['select_index'] == -1


def test_dingtalk_extract_select_from_builtin_result_dict():
    inputs = _dingtalk_extract_component_inputs({'selectResult': {'index': 1, 'value': 'B'}})

    assert inputs == {'select': 'B'}


def test_dingtalk_extract_select_from_template_param_string():
    inputs = _dingtalk_extract_component_inputs({'select': '{"index": 1, "value": "B"}'})

    assert inputs == {'select': '{"index": 1, "value": "B"}'}


def test_dingtalk_extract_input_and_select_together():
    inputs = _dingtalk_extract_component_inputs(
        {
            'inputResult': {'value': 'looks good'},
            '__built_in_selectResult__': {'index': 0, 'value': 'A'},
        }
    )

    assert inputs == {'input': 'looks good', 'select': 'A'}


def test_dingtalk_extract_component_inputs_strips_card_line_endings():
    inputs = _dingtalk_extract_component_inputs(
        {
            'inputResult': {'value': '回复我测试\r\n'},
            'selectResult': {'value': '1\r'},
        }
    )

    assert inputs == {'input': '回复我测试', 'select': '1'}


def test_dingtalk_pending_input_defs_includes_file_fields():
    pending = _dingtalk_pending_input_defs(
        {
            'input_defs': [
                {'output_variable_name': 'comment', 'type': 'paragraph'},
                {'output_variable_name': 'files', 'type': 'file-list'},
            ],
            'inputs': {'comment': 'ready'},
        }
    )

    assert [field['output_variable_name'] for field in pending] == ['files']


def test_dingtalk_completed_input_lines_include_text_and_select_values():
    lines = _dingtalk_completed_input_lines(
        {
            'all_input_defs': [
                {'output_variable_name': 'comment', 'type': 'paragraph'},
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                },
            ],
            'inputs': {'comment': 'looks good', 'choice': 'B'},
        }
    )

    assert lines == ['✅ comment：looks good', '✅ choice：B']


def test_dingtalk_completed_inputs_are_not_repeated_when_already_interleaved():
    form_data = {
        'all_input_defs': [
            {'output_variable_name': 'us_input', 'type': 'paragraph'},
            {'output_variable_name': 'xiala', 'type': 'select'},
        ],
        'inputs': {'us_input': '回复我测试\r', 'xiala': '1'},
    }
    form_content = '你好\n请输入你的问题\n✅ us_input：回复我测试\n请选择你的答案\n✅ xiala：1'

    assert _dingtalk_missing_completed_input_lines(form_data, form_content) == []


def test_dingtalk_completed_inputs_are_appended_when_template_does_not_render_them():
    form_data = {
        'all_input_defs': [{'output_variable_name': 'comment', 'type': 'paragraph'}],
        'inputs': {'comment': 'ready'},
    }

    assert _dingtalk_missing_completed_input_lines(form_data, 'Please review') == ['✅ comment：ready']


def test_dingtalk_clean_form_content_uses_all_input_defs():
    content = _dingtalk_clean_form_content(
        {
            'raw_form_content': 'Hello\n\n{{#$output.comment#}}\n\n{{#$output.choice#}}\n',
            'input_defs': [],
            'all_input_defs': [
                {'output_variable_name': 'comment', 'type': 'paragraph'},
                {'output_variable_name': 'choice', 'type': 'select'},
            ],
        }
    )

    assert content == 'Hello'


def test_dingtalk_field_stage_keeps_prior_prompts_and_completed_values():
    content = _dingtalk_clean_form_content(
        {
            '_current_input_field': 'choice',
            'raw_form_content': ('Question\n{{#$output.comment#}}\nChoose an answer\n{{#$output.choice#}}'),
            'form_content': 'Choose an answer',
            'input_defs': [
                {'output_variable_name': 'comment', 'type': 'paragraph'},
                {'output_variable_name': 'choice', 'type': 'select'},
            ],
            'inputs': {'comment': 'hello'},
        }
    )

    assert '{{#$output.' not in content
    assert content.index('Question') < content.index('comment')
    assert content.index('comment') < content.index('Choose an answer')


def test_dingtalk_final_action_stage_interleaves_prompts_and_completed_values():
    content = _dingtalk_clean_form_content(
        {
            '_action_select_only': True,
            'raw_form_content': ('11\nQuestion\n{{#$output.comment#}}\nChoose an answer\n{{#$output.choice#}}'),
            'all_input_defs': [
                {'output_variable_name': 'comment', 'type': 'paragraph'},
                {'output_variable_name': 'choice', 'type': 'select'},
            ],
            'inputs': {'comment': 'hello', 'choice': 'B'},
        }
    )

    assert '{{#$output.' not in content
    assert content.startswith('11\nQuestion')
    assert content.index('Question') < content.index('comment')
    assert content.index('comment') < content.index('Choose an answer')
    assert content.index('Choose an answer') < content.index('choice')


def test_dingtalk_card_markdown_preserves_internal_line_breaks():
    assert _dingtalk_card_markdown('11\nQuestion\nCompleted') == '11<br>Question<br>Completed'


def _build_card_action_adapter() -> DingTalkAdapter:
    adapter = DingTalkAdapter.model_construct(
        card_state={
            'card-1': {
                'session_key': 'group_group-1',
                'launcher_type': 'group',
                'launcher_id': 'group-1',
                'sender_user_id': 'initiator-1',
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'approve', 'title': 'Approve'}],
                'node_title': 'Review',
                'form_content': 'Please review',
                'input_defs': [],
                'inputs': {},
            }
        },
        active_turn_card={},
        active_turn_text={},
    )
    adapter.logger = AsyncMock()
    adapter.ap = MagicMock()
    adapter.ap.platform_mgr.bots = []
    adapter.ap.query_pool.add_query = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_dingtalk_group_card_action_uses_clicker_as_sender():
    adapter = _build_card_action_adapter()

    with patch.object(DingTalkAdapter, '_mark_card_resolved', new=AsyncMock()) as mark_resolved:
        await adapter._on_card_action(
            {
                'out_track_id': 'card-1',
                'user_id': 'reviewer-2',
                'action_id': 'approve',
                'params': {},
            }
        )
        await asyncio.sleep(0)

    call = adapter.ap.query_pool.add_query.await_args
    assert call.kwargs['launcher_id'] == 'group-1'
    assert call.kwargs['sender_id'] == 'reviewer-2'
    assert call.kwargs['message_event'].sender.id == 'reviewer-2'
    mark_resolved.assert_awaited_once()


@pytest.mark.asyncio
async def test_dingtalk_unknown_card_action_is_rejected():
    adapter = _build_card_action_adapter()

    await adapter._on_card_action(
        {
            'out_track_id': 'card-1',
            'user_id': 'reviewer-2',
            'action_id': 'not-on-card',
            'params': {},
        }
    )

    adapter.ap.query_pool.add_query.assert_not_awaited()
    adapter.logger.warning.assert_awaited_once()
