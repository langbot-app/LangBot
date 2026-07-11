"""Tests for Lark adapter helper behavior."""

from langbot.pkg.platform.sources.lark import (
    LarkAdapter,
    _lark_clean_form_content,
    _lark_completed_input_lines,
    _lark_current_input_defs,
    _lark_extract_action_form_inputs,
    _lark_should_update_stream_element,
    _lark_visible_form_content,
)


def test_lark_current_input_defs_only_returns_active_stage():
    input_defs = [
        {'output_variable_name': 'us_input', 'type': 'paragraph'},
        {'output_variable_name': 'xiala', 'type': 'select'},
    ]

    assert _lark_current_input_defs(
        {
            '_current_input_field': 'xiala',
            'input_defs': input_defs,
        }
    ) == [input_defs[1]]
    assert (
        _lark_current_input_defs(
            {
                '_action_select_only': True,
                'input_defs': input_defs,
            }
        )
        == []
    )


def test_lark_form_field_elements_only_render_active_stage():
    adapter = LarkAdapter.model_construct()
    form_data = {
        '_current_input_field': 'xiala',
        'input_defs': [
            {'output_variable_name': 'us_input', 'type': 'paragraph'},
            {
                'output_variable_name': 'xiala',
                'type': 'select',
                'option_source': {'type': 'constant', 'value': ['1', '2']},
            },
        ],
    }

    elements, input_name_map, file_help_lines = adapter._build_lark_form_field_elements(form_data)

    assert len(elements) == 1
    assert elements[0]['tag'] == 'select_static'
    assert elements[0]['label']['content'] == 'xiala'
    assert list(input_name_map.values()) == ['xiala']
    assert file_help_lines == []


def test_lark_form_stage_skips_closed_streaming_element_update():
    assert not _lark_should_update_stream_element(
        resume_from=False,
        form_data={'_current_input_field': 'xiala'},
        msg_seq=1,
        is_final=True,
    )
    assert _lark_should_update_stream_element(
        resume_from=False,
        form_data=None,
        msg_seq=1,
        is_final=True,
    )


def test_lark_final_action_stage_interleaves_prompts_and_completed_values():
    form_content = _lark_visible_form_content(
        {
            '_action_select_only': True,
            'raw_form_content': ('11\nQuestion\n{{#$output.us_input#}}\nChoose an answer\n{{#$output.xiala#}}\n'),
            'all_input_defs': [
                {'output_variable_name': 'us_input', 'type': 'paragraph'},
                {'output_variable_name': 'xiala', 'type': 'select'},
            ],
            'inputs': {'us_input': 'hello', 'xiala': '2'},
        }
    )

    assert '{{#$output.' not in form_content
    assert form_content.startswith('11\nQuestion')
    assert form_content.index('Question') < form_content.index('us_input')
    assert form_content.index('us_input') < form_content.index('Choose an answer')
    assert form_content.index('Choose an answer') < form_content.index('xiala')


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
