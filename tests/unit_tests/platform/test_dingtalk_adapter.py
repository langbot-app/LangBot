"""Tests for DingTalk adapter helper behavior."""

from langbot.pkg.platform.sources.dingtalk import (
    _dingtalk_clean_form_content,
    _dingtalk_completed_input_lines,
    _dingtalk_extract_component_inputs,
    _dingtalk_form_component_params,
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

    assert lines == ['✅ 已填写 comment：**looks good**', '✅ 已选择 choice：**B**']


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
