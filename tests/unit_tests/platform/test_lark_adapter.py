"""Tests for Lark adapter helper behavior."""

import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot.pkg.platform.sources.lark import (
    LarkAdapter,
    _decode_lark_base64_limited,
    _lark_clean_form_content,
    _lark_completed_input_lines,
    _lark_current_input_defs,
    _lark_extract_action_form_inputs,
    _lark_final_layout_texts,
    _lark_should_update_stream_element,
    _lark_visible_form_content,
)


def test_lark_base64_decode_is_bounded(monkeypatch):
    import langbot.pkg.platform.sources.lark as lark_module

    monkeypatch.setattr(lark_module, '_MAX_LARK_MEDIA_BYTES', 4)

    with pytest.raises(ValueError, match='exceeds'):
        _decode_lark_base64_limited('A' * 12)


def test_lark_threadsafe_callbacks_are_bounded():
    adapter = LarkAdapter.model_construct()
    adapter.threadsafe_event_lock = threading.Lock()
    adapter.threadsafe_event_futures = {MagicMock(done=MagicMock(return_value=False)) for _ in range(100)}

    async def callback():
        raise AssertionError('rejected callback must not run')

    assert adapter._schedule_threadsafe_event(callback()) is None
    assert len(adapter.threadsafe_event_futures) == 100


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
        '✅ us_input：你好',
        '✅ xiala：or',
        '✅ files：2 file(s)',
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

    assert lines == ['✅ xiala：B']


def test_lark_final_layout_texts_normal_round_drops_resume_placeholder():
    """Non-resume final chunk: the reply must land in the main element only.

    Regression: rendering the resume placeholder too duplicated the reply,
    because the accumulated streaming text equals the final text on a normal
    round (e.g. 'It is Sep 1, 2026.\nIt is Sep 1, 2026.' in the card).
    """
    main_text, resume_text = _lark_final_layout_texts(
        resume_from=False,
        text_message='It is Sep 1, 2026, 15:09:15.',
        pre_pause_cached=None,
        resume_cached='It is Sep 1, 2026, 15:09:15.',
    )

    assert main_text == 'It is Sep 1, 2026, 15:09:15.'
    assert resume_text == ''


def test_lark_final_layout_texts_resume_round_keeps_both_segments():
    """Dify HITL resume final chunk: pre-pause text and resumed text differ,
    both segments stay visible."""
    main_text, resume_text = _lark_final_layout_texts(
        resume_from=True,
        text_message='resumed answer',
        pre_pause_cached='partial answer before pause',
        resume_cached='resumed answer',
    )

    assert main_text == 'partial answer before pause'
    assert resume_text == 'resumed answer'


def test_lark_final_layout_texts_resume_round_without_pre_pause_falls_back():
    main_text, resume_text = _lark_final_layout_texts(
        resume_from=True,
        text_message='answer',
        pre_pause_cached=None,
        resume_cached='answer',
    )

    assert main_text == 'answer'
    assert resume_text == 'answer'


def test_lark_final_layout_texts_resume_round_empty_pre_pause_kept_empty():
    """Dify paused before emitting any text: the pre-pause cache is a valid
    empty string and must NOT be treated as a cache miss.

    Regression: `pre_pause_cached or text_message` fell back to the full
    text, so the final card rendered ('resumed answer', 'resumed answer')
    and duplicated the reply.
    """
    main_text, resume_text = _lark_final_layout_texts(
        resume_from=True,
        text_message='resumed answer',
        pre_pause_cached='',
        resume_cached='resumed answer',
    )

    assert main_text == ''
    assert resume_text == 'resumed answer'


def _build_resume_final_chunk_adapter(message_text: str):
    """Build a LarkAdapter whose card state mimics a Dify HITL round that
    paused before emitting any text, then resumed and completed."""
    adapter = LarkAdapter.model_construct(
        api_client=MagicMock(),
        message_converter=MagicMock(yiri2target=AsyncMock(return_value=([[{'tag': 'text', 'text': message_text}]], []))),
    )
    adapter.config = {'app_type': 'self'}
    LarkAdapter.get_app_access_token = lambda self: None
    LarkAdapter.get_tenant_access_token = lambda self, tenant_key: None
    adapter.card_id_dict = {'msg-1': 'card-1'}
    adapter.card_streaming_text = {'card-1': message_text}
    adapter.card_pre_pause_text = {'card-1': ''}
    adapter.card_resume_transitioned = {'card-1'}
    adapter.card_sequence_dict = {}
    adapter.card_last_accessed = {}
    adapter.card_cleanup_at = 0.0
    adapter.card_id_to_source_ids = {}
    adapter.reply_message_card_ids = {}
    adapter.card_form_content = {}
    adapter.card_form_input_defs = {}
    adapter.card_form_inputs = {}
    adapter._update_card_layout = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_reply_message_chunk_resume_final_with_empty_pre_pause_keeps_main_empty():
    """End-to-end regression via reply_message_chunk: Dify paused before any
    text, so the pre-pause cache is ''. The final card update must render the
    resumed answer only once (empty main text + resume placeholder), not
    twice as ('resumed answer', 'resumed answer')."""
    adapter = _build_resume_final_chunk_adapter('resumed answer')

    bot_message = MagicMock(
        resp_message_id='msg-1',
        msg_sequence=1,
        spec=['resp_message_id', 'msg_sequence', '_resume_from_form'],
    )
    bot_message._resume_from_form = True
    message_source = MagicMock(source_platform_object=None)

    await adapter.reply_message_chunk(
        message_source,
        bot_message,
        MagicMock(),
        is_final=True,
    )

    adapter._update_card_layout.assert_awaited_once()
    layout_kwargs = adapter._update_card_layout.await_args.kwargs
    assert layout_kwargs['text_message'] == ''
    assert layout_kwargs['resume_placeholder_text'] == 'resumed answer'
