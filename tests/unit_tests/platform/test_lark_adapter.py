"""Tests for Lark adapter helper behavior."""

from langbot.pkg.platform.sources.lark import (
    _lark_clean_form_content,
    _lark_completed_input_lines,
    _lark_extract_action_form_inputs,
)


def test_lark_completed_input_lines_include_text_select_and_files():
    lines = _lark_completed_input_lines(
        {
            'all_input_defs': [
                {'output_variable_name': 'us_input', 'type': 'paragraph'},
                {'output_variable_name': 'xiala', 'type': 'select'},
                {'output_variable_name': 'files', 'type': 'file-list'},
            ],
            'inputs': {
                'us_input': '你好',
                'xiala': 'or',
                'files': [{'upload_file_id': 'file-1'}, {'upload_file_id': 'file-2'}],
            },
        }
    )

    assert lines == [
        '✅ 已填写 us_input：**你好**',
        '✅ 已选择 xiala：**or**',
        '✅ 已上传 files：**2 file(s)**',
    ]


def test_lark_clean_form_content_removes_all_input_placeholders():
    content = _lark_clean_form_content(
        '人工介入\n\n{{#$output.us_input#}}\n\n{{#$output.xiala#}}\n',
        [
            {'output_variable_name': 'us_input', 'type': 'paragraph'},
            {'output_variable_name': 'xiala', 'type': 'select'},
        ],
    )

    assert content == '人工介入'


def test_lark_extract_action_form_inputs_from_json_form_value():
    class Action:
        form_value = '{"Input_1_us_input_abcd12": "hello", "Select_2_xiala_abcd12": "B"}'
        input_value = None
        option = None
        name = None

    inputs = _lark_extract_action_form_inputs(
        Action(),
        {
            'input_name_map': {
                'Input_1_us_input_abcd12': 'us_input',
                'Select_2_xiala_abcd12': 'xiala',
            }
        },
    )

    assert inputs == {'us_input': 'hello', 'xiala': 'B'}


def test_lark_extract_action_form_inputs_from_webhook_dict_action():
    inputs = _lark_extract_action_form_inputs(
        {
            'form_value': {
                'Input_1_us_input_abcd12': 'hello',
                'Select_2_xiala_abcd12': {'value': 'B', 'text': {'content': 'Option B'}},
            }
        },
        {
            'input_name_map': {
                'Input_1_us_input_abcd12': 'us_input',
                'Select_2_xiala_abcd12': 'xiala',
            }
        },
    )

    assert inputs == {'us_input': 'hello', 'xiala': {'value': 'B', 'text': {'content': 'Option B'}}}


def test_lark_extract_action_form_inputs_maps_dotted_component_names():
    inputs = _lark_extract_action_form_inputs(
        {
            'form_value': {
                'Form_1_token_abcd12.Input_1_us_input_abcd12': 'hello',
            }
        },
        {
            'input_name_map': {
                'Input_1_us_input_abcd12': 'us_input',
            }
        },
    )

    assert inputs == {'us_input': 'hello'}


def test_lark_completed_input_lines_display_select_value_from_object():
    lines = _lark_completed_input_lines(
        {
            'all_input_defs': [
                {'output_variable_name': 'xiala', 'type': 'select'},
            ],
            'inputs': {'xiala': {'value': 'B', 'text': {'content': 'Option B'}}},
        }
    )

    assert lines == ['✅ 已选择 xiala：**B**']
