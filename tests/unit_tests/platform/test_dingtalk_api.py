"""Tests for DingTalk API payload helpers."""

import base64
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

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
    response = type('Response', (), {'status_code': 200, 'json': lambda self: {}})()
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
            'autoLayout': 'true',
        }
    }
    assert original_params == {'content': 'hello'}


def _voice_client():
    from langbot.libs.dingtalk_api.api import DingTalkClient

    client = DingTalkClient.__new__(DingTalkClient)
    client.logger = None
    client._upload_media = AsyncMock(return_value='media-1')
    client._send_robot_message = AsyncMock(return_value={'ok': True})
    return client


@pytest.mark.asyncio
async def test_send_voice_transcodes_to_ogg_and_sends_sample_audio(monkeypatch):
    from langbot.pkg.utils import audio as audio_utils
    from langbot_plugin.api.entities.builtin.platform.message import Voice

    transcode = AsyncMock(return_value=b'OggS' + b'\x00' * 32)
    monkeypatch.setattr(audio_utils, 'transcode_audio', transcode)
    client = _voice_client()
    voice = Voice(base64='data:audio/mpeg;base64,' + base64.b64encode(b'ID3' + b'\x00' * 32).decode(), length=5)

    await client.send_voice(voice, 'incoming')

    transcode.assert_awaited_once()
    assert transcode.await_args.args[1] == 'ogg'
    client._upload_media.assert_awaited_once()
    name, _body, media_type = client._upload_media.await_args.args
    assert (name, media_type) == ('voice.ogg', 'voice')
    msg_key, params, incoming = client._send_robot_message.await_args.args
    assert msg_key == 'sampleAudio'
    assert params == {'mediaId': 'media-1', 'duration': '5000'}
    assert incoming == 'incoming'


@pytest.mark.asyncio
async def test_send_voice_over_limit_is_sent_as_file(monkeypatch):
    from langbot.pkg.utils import audio as audio_utils
    from langbot_plugin.api.entities.builtin.platform.message import Voice

    monkeypatch.setattr(audio_utils, 'transcode_audio', AsyncMock())
    client = _voice_client()
    voice = Voice(base64='data:audio/ogg;base64,' + base64.b64encode(b'OggS' + b'\x00' * 32).decode(), length=90)

    await client.send_voice(voice, 'incoming')

    audio_utils.transcode_audio.assert_not_awaited()
    assert client._upload_media.await_args.args[2] == 'file'
    msg_key, params, _ = client._send_robot_message.await_args.args
    assert msg_key == 'sampleFile'
    assert params == {'mediaId': 'media-1', 'fileName': 'voice.ogg', 'fileType': 'ogg'}


@pytest.mark.asyncio
async def test_send_voice_falls_back_to_file_when_transcode_fails(monkeypatch):
    from langbot.pkg.utils import audio as audio_utils
    from langbot_plugin.api.entities.builtin.platform.message import Voice

    monkeypatch.setattr(audio_utils, 'transcode_audio', AsyncMock(side_effect=RuntimeError('no ffmpeg')))
    client = _voice_client()
    voice = Voice(base64='data:audio/mpeg;base64,' + base64.b64encode(b'ID3' + b'\x00' * 32).decode(), length=3)

    await client.send_voice(voice, 'incoming')

    assert client._upload_media.await_args.args[2] == 'file'
    msg_key, params, _ = client._send_robot_message.await_args.args
    assert msg_key == 'sampleFile'
    assert params['fileName'] == 'voice.mp3'


def test_estimate_audio_duration_reads_ogg_opus_granule_position():
    from langbot.pkg.utils import audio as audio_utils

    def page(granule: int, payload: bytes) -> bytes:
        return b'OggS\x00\x00' + granule.to_bytes(8, 'little') + b'\x00' * 12 + payload

    data = page(0, b'OpusHead' + b'\x00' * 11) + page(0, b'OpusTags') + page(48000 * 3, b'\x00' * 8)

    assert audio_utils.detect_audio_format(data) == 'opus'
    assert audio_utils.estimate_audio_duration(data) == 3.0


@pytest.mark.asyncio
async def test_extract_voice_bytes_ignores_non_audio_mime_hint():
    from langbot.pkg.utils import audio as audio_utils
    from langbot_plugin.api.entities.builtin.platform.message import Voice

    voice = Voice(base64='data:application/octet-stream;base64,' + base64.b64encode(b'unrecognized').decode())
    _, fmt = await audio_utils.extract_voice_bytes(voice)
    assert fmt == 'unknown'

    voice = Voice(base64='data:audio/mpeg;base64,' + base64.b64encode(b'unrecognized').decode())
    _, fmt = await audio_utils.extract_voice_bytes(voice)
    assert fmt == 'mp3'
