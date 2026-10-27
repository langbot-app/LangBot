"""Tests for DingTalk A2UI API payloads."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from langbot.libs.dingtalk_api.a2ui import create_text_card_messages, update_text_card_messages
from langbot.libs.dingtalk_api.api import DingTalkClient


def _client(http_client):
    @asynccontextmanager
    async def client_context():
        yield http_client

    client = object.__new__(DingTalkClient)
    client.access_token = 'access-token'
    client.robot_code = 'robot-code'
    client.key = 'client-id'
    client.logger = None
    client.check_access_token = AsyncMock(return_value=True)
    client.get_access_token = AsyncMock()
    client._http_client_context = client_context
    return client


def _response(result=None):
    payload = {'success': True, 'result': result or {}}
    return type('Response', (), {'status_code': 200, 'json': lambda self: payload})()


def test_text_card_keeps_brand_when_content_updates():
    components = create_text_card_messages('surface-id', 'hello')[2]['updateComponents']['components']
    by_id = {component['id']: component for component in components}

    assert by_id['root']['children'] == ['langbot-brand', 'content']
    assert by_id['langbot-brand']['children'] == ['langbot-brand-icon', 'langbot-brand-link']
    assert by_id['langbot-brand-icon']['url'] == 'https://langbot.app/logo-blue.png'
    assert by_id['langbot-brand-icon']['previewEnabled'] is False
    assert by_id['langbot-brand-link']['component'] == 'Markdown'
    assert by_id['langbot-brand-link']['content'] == (
        '[LangBot](https://langbot.app?utm_source=dingtalk&utm_medium=bot_card&utm_campaign=langbot)'
    )
    assert update_text_card_messages('surface-id', 'done')[0]['updateDataModel']['path'] == '/content'


@pytest.mark.asyncio
async def test_create_card_for_target_uses_robot_a2ui_delivery():
    client = _client(None)
    client.create_and_deliver_ai_card = AsyncMock(return_value={})

    card, track_id = await client.create_and_card_for_target('person', 'user-1')

    assert card == {'surface_id': f'langbot-{track_id}'}
    request = client.create_and_deliver_ai_card.await_args.kwargs
    assert request['open_space_id'] == 'dtv1.card//im_robot.user-1'
    assert request['is_group'] is False
    assert request['a2ui_messages'][2]['updateComponents']['components'][0]['children'][0] == 'langbot-brand'


@pytest.mark.asyncio
async def test_create_ai_card_uses_group_robot_delivery_model():
    post = AsyncMock(
        return_value=_response(
            {
                'outTrackId': 'track-id',
                'deliverResults': [{'spaceType': 'IM_GROUP', 'success': True}],
            }
        )
    )
    client = _client(type('HttpClient', (), {'post': post})())

    result = await client.create_and_deliver_ai_card(
        out_track_id='track-id',
        open_space_id='dtv1.card//im_group.group-id',
        is_group=True,
        a2ui_messages=create_text_card_messages('surface-id', 'hello'),
        summary='hello',
    )

    request = post.await_args
    body = request.kwargs['json']
    assert request.args[0].endswith('/v1.0/card/ai/instances/createAndDeliver')
    assert result['outTrackId'] == 'track-id'
    assert body['imGroupOpenDeliverModel'] == {'robotCode': 'robot-code'}
    assert body['imGroupOpenSpaceModel'] == {'supportForward': False}
    assert 'imRobotOpenDeliverModel' not in body
    assert 'cardTemplateId' not in body
    assert body['protocolVersion'] == '1.0'
    assert body['flowStatus'] == 'PROCESSING'
    assert all(isinstance(message, str) for message in body['a2uiMessages'])
    assert json.loads(body['a2uiMessages'][0])['createSurface']['surfaceId'] == 'surface-id'


@pytest.mark.asyncio
async def test_create_ai_card_uses_single_chat_robot_delivery_model():
    post = AsyncMock(return_value=_response({'deliverResults': [{'spaceType': 'IM_ROBOT', 'success': True}]}))
    client = _client(type('HttpClient', (), {'post': post})())

    await client.create_and_deliver_ai_card(
        out_track_id='track-id',
        open_space_id='dtv1.card//im_robot.user-id',
        is_group=False,
        a2ui_messages=create_text_card_messages('surface-id'),
    )

    body = post.await_args.kwargs['json']
    assert body['imRobotOpenDeliverModel'] == {'robotCode': 'robot-code'}
    assert body['imRobotOpenSpaceModel'] == {'supportForward': False}
    assert 'imGroupOpenDeliverModel' not in body


@pytest.mark.asyncio
async def test_update_ai_card_uses_a2ui_delta_and_idempotency_key():
    put = AsyncMock(return_value=_response({'outTrackId': 'track-id', 'flowStatus': 'FINISH'}))
    client = _client(type('HttpClient', (), {'put': put})())

    await client.update_ai_card(
        out_track_id='track-id',
        out_update_id='update-id',
        flow_status='FINISH',
        a2ui_messages=update_text_card_messages('surface-id', 'done'),
    )

    request = put.await_args
    body = request.kwargs['json']
    assert request.args[0].endswith('/v1.0/card/ai/instances/update')
    assert body['outTrackId'] == 'track-id'
    assert body['outUpdateId'] == 'update-id'
    assert body['flowStatus'] == 'FINISH'
    assert json.loads(body['a2uiMessages'][0])['updateDataModel']['path'] == '/content'


@pytest.mark.asyncio
async def test_create_ai_card_rejects_failed_delivery_result():
    post = AsyncMock(
        return_value=_response({'deliverResults': [{'spaceType': 'IM_GROUP', 'success': False, 'errorMsg': 'denied'}]})
    )
    client = _client(type('HttpClient', (), {'post': post})())

    with pytest.raises(RuntimeError, match='delivery failed'):
        await client.create_and_deliver_ai_card(
            out_track_id='track-id',
            open_space_id='dtv1.card//im_group.group-id',
            is_group=True,
            a2ui_messages=create_text_card_messages('surface-id'),
        )
