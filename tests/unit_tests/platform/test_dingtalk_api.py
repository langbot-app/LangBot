"""Tests for DingTalk API payload helpers."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from langbot.libs.dingtalk_api.api import DingTalkClient, _stringify_card_param_map
from langbot.pkg.utils import httpclient


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


async def test_create_card_embeds_layout_config_as_template_parameter(monkeypatch):
    response = type('Response', (), {'status_code': 200})()
    post = AsyncMock(return_value=response)

    @asynccontextmanager
    async def client_context():
        yield type('HttpClient', (), {'post': post})()

    client = object.__new__(DingTalkClient)
    client.access_token = 'access-token'
    client.robot_code = 'robot-code'
    client.key = 'client-id'
    client.logger = None
    client.check_access_token = AsyncMock(return_value=True)
    client._http_client_context = client_context
    monkeypatch.setattr(httpclient, 'response_text', AsyncMock(return_value='{}'))

    original_params = {'content': 'hello'}
    delivered = await client.create_and_deliver_card(
        card_template_id='template-id',
        out_track_id='track-id',
        open_space_id='dtv1.card//IM_ROBOT.user-id',
        is_group=False,
        card_param_map=original_params,
        card_data_config={'autoLayout': True},
    )

    request_body = post.await_args.kwargs['json']
    assert delivered is True
    assert request_body['cardData'] == {
        'cardParamMap': {
            'content': 'hello',
            'config': '{"autoLayout": true}',
        }
    }
    assert original_params == {'content': 'hello'}
