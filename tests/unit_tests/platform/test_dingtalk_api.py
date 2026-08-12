"""Tests for DingTalk API payload helpers."""

import json

from langbot.libs.dingtalk_api.api import _stringify_card_param_map


def test_dingtalk_card_param_map_stringifies_select_component_arrays():
    params = _stringify_card_param_map(
        {
            'content': 'Pick one',
            'btns': json.dumps([{'text': 'OK'}], ensure_ascii=False),
            'select_options': ['A', 'B'],
            'index_o': [
                {
                    'value': 'A',
                    'text': {'zh_CN': 'A', 'en_US': 'A'},
                }
            ],
            'test_index': [
                {
                    'value': 'A',
                    'text': {'zh_CN': 'A', 'en_US': 'A'},
                }
            ],
            'select_index': -1,
        }
    )

    assert params['content'] == 'Pick one'
    assert params['btns'] == '[{"text": "OK"}]'
    assert params['select_options'] == '["A", "B"]'
    assert json.loads(params['index_o'])[0]['value'] == 'A'
    assert json.loads(params['test_index'])[0]['value'] == 'A'
    assert params['select_index'] == '-1'


def test_dingtalk_card_param_map_stringifies_unregistered_structures():
    params = _stringify_card_param_map({'other': ['A'], 'empty': None})

    assert params['other'] == '["A"]'
    assert params['empty'] == ''
