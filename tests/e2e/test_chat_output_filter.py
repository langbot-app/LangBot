import json
import time

import pytest
from websockets.sync.client import connect

from tests.e2e import test_runner_plugin_runtime as runtime
from tests.unit_tests.platform.onebot_mock import OneBotMock
from tools.regression.http_bot import signed_headers

runner_client = runtime.runner_client
runner_e2e_tmpdir = runtime.runner_e2e_tmpdir
runner_e2e_port = runtime.runner_e2e_port
runner_runtime_ports = runtime.runner_runtime_ports
runner_runtime_process = runtime.runner_runtime_process
runner_langbot_process = runtime.runner_langbot_process


@pytest.fixture(scope='session')
def runner_e2e_config_path(runner_e2e_tmpdir, runner_e2e_port, runner_runtime_ports):
    config = runtime.runner_e2e_config_path.__wrapped__(runner_e2e_tmpdir, runner_e2e_port, runner_runtime_ports)
    words = runner_e2e_tmpdir / 'data/metadata/sensitive-words.json'
    words.parent.mkdir(parents=True, exist_ok=True)
    words.write_text(json.dumps({'words': ['e2e echo'], 'mask_word': 'MASKED', 'mask': '*'}))
    return config


@pytest.mark.e2e
def test_chat_output_filter_on_wire(runner_client, runner_e2e_tmpdir):
    client = runner_client
    token = runtime._init_and_auth(client)
    runtime._ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    chat = runtime._create_boundary_pipeline(client, token)
    peer = OneBotMock()
    for enabled in (False, True):
        for adapter in ('onebot-v11', 'http_bot'):
            onebot = adapter == 'onebot-v11'
            response = client.post(
                '/api/v1/platform/bots',
                headers={'Authorization': 'Bearer ' + token},
                json={
                    'name': f'{adapter} filter {enabled}',
                    'adapter': adapter,
                    'enable': True,
                    'adapter_config': {'connection_mode': 'reverse_ws', 'access-token': 'onebot-qa', 'self_id': '42'}
                    if onebot
                    else {'inbound_secret': 'qa-sign', 'signature_required': True},
                    'event_bindings': [
                        {
                            'id': 'chat',
                            'event_pattern': 'message.received',
                            'target_type': 'pipeline',
                            'target_uuid': chat,
                        }
                    ],
                    'message_policy': {
                        'trigger': {'group-respond-rules': {'enabled': False}},
                        'safety': {'content-filter': {'scope': 'output-msg', 'check-sensitive-words': enabled}},
                        'output': {'misc': {'at-sender': False, 'quote-origin': False}},
                    },
                },
            ).json()
            assert response['code'] == 0, response
            bot = response['data']['uuid']
            if onebot:
                uri = f'ws://127.0.0.1:{client.base_url.port}/bots/{bot}/onebot/v11/ws'
                with connect(
                    uri,
                    proxy=None,
                    additional_headers={
                        'Authorization': 'Bearer onebot-qa',
                        'X-Self-ID': '42',
                        'X-Client-Role': 'Universal',
                    },
                ) as socket_peer:
                    for kind in ('private', 'group'):
                        incoming = peer.message(
                            kind,
                            'friend' if kind == 'private' else 'normal',
                            [{'type': 'text', 'data': {'text': 'hello'}}],
                        )
                        socket_peer.send(json.dumps(incoming | {'raw_message': 'hello', 'time': int(time.time())}))
                        deadline = time.monotonic() + 30
                        while True:
                            request = json.loads(socket_peer.recv(timeout=max(0, deadline - time.monotonic())))
                            socket_peer.send(json.dumps(peer.handle(request) | {'echo': request['echo']}))
                            if request['action'] in ('send_msg', 'send_private_msg', 'send_group_msg'):
                                break
                        assert request['params']['message'] == [
                            {'type': 'text', 'data': {'text': 'MASKED: hello' if enabled else 'e2e echo: hello'}}
                        ]
            else:
                for kind in ('person', 'group'):
                    body = json.dumps(
                        {'session_type': kind, 'session_id': 'qa', 'message': [{'type': 'Plain', 'text': 'hello'}]}
                    ).encode()
                    reply = client.post(
                        f'/bots/{bot}/sync', content=body, headers=signed_headers(body, 'qa-sign')
                    ).json()
                    assert reply['code'] == 0, reply
                    assert reply['data']['message'] == [{'type': 'Plain', 'text': 'e2e echo: hello'}]
