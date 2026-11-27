import json
import time

import pytest

from tests.e2e import test_runner_plugin_runtime as runtime
from tests.e2e import test_llm_request_chain as wire
from tests.e2e.test_local_runner_fake_provider import LOCAL_RUNNER_ID, _package_local_agent_plugin
from tools.regression.http_bot import signed_headers

runner_runtime_ports = runtime.runner_runtime_ports
runner_runtime_process = runtime.runner_runtime_process
runner_langbot_process = runtime.runner_langbot_process
runner_e2e_tmpdir = runtime.runner_e2e_tmpdir
runner_e2e_port = runtime.runner_e2e_port
runner_e2e_config_path = runtime.runner_e2e_config_path
runner_client = runtime.runner_client
provider_wire = wire.provider_wire


@pytest.mark.e2e
def test_local_agent_without_model(runner_client, runner_e2e_tmpdir):
    client = runner_client
    token = runtime._init_and_auth(client)
    headers = {'Authorization': 'Bearer ' + token}
    runtime._install_qa_plugin(client, token, _package_local_agent_plugin(runner_e2e_tmpdir), LOCAL_RUNNER_ID)
    assert LOCAL_RUNNER_ID in runtime._wait_for_qa_runner(client, token, runner_id=LOCAL_RUNNER_ID)

    def api(method, path, **kwargs):
        result = client.request(method, '/api/v1/' + path, headers=headers, **kwargs).json()
        assert result['code'] == 0, result
        return result['data']

    agent = api(
        'POST',
        'agents',
        json={
            'name': 'No model',
            'kind': 'agent',
            'supported_event_patterns': ['message.*'],
            'config': {'runner': {'id': LOCAL_RUNNER_ID}, 'runner_config': {LOCAL_RUNNER_ID: {}}},
        },
    )['uuid']
    bot = api(
        'POST',
        'platform/bots',
        json={
            'name': 'No model',
            'adapter': 'http_bot',
            'enable': True,
            'adapter_config': {'inbound_secret': 'qa-sign', 'signature_required': True},
            'event_bindings': [{'event_pattern': 'message.received', 'target_type': 'agent', 'target_uuid': agent}],
            'message_policy': {'trigger': {'group-respond-rules': {'enabled': False}}},
        },
    )['uuid']
    for index, kind in enumerate(('person', 'group'), start=1):
        body = json.dumps(
            {'session_type': kind, 'session_id': kind, 'message': [{'type': 'Plain', 'text': 'missing model'}]}
        ).encode()
        reply = client.post('/bots/' + bot, content=body, headers=signed_headers(body, 'qa-sign'))
        assert reply.status_code == 202
        deadline = time.monotonic() + 30
        while True:
            runs = api('GET', f'agents/{agent}/runs')['items']
            if len(runs) == index and all(run['status'] == 'failed' for run in runs):
                break
            assert time.monotonic() < deadline, [(run['status'], run.get('status_reason')) for run in runs]
            time.sleep(0.2)
        for run in runs:
            events = api('GET', f'agents/{agent}/runs/{run["run_id"]}/events')['items']
            assert any(
                event['type'] == 'run.failed' and 'runner.no_model' in json.dumps(event['data']) for event in events
            ), [(event['type'], event['data']) for event in events if event['type'] == 'run.failed']


@pytest.mark.e2e
def test_session_model_and_retry(runner_client, runner_e2e_tmpdir, provider_wire):
    client = runner_client
    token = runtime._init_and_auth(client)
    client.headers['Authorization'] = f'Bearer {token}'
    runtime._install_qa_plugin(client, token, _package_local_agent_plugin(runner_e2e_tmpdir), LOCAL_RUNNER_ID)
    assert LOCAL_RUNNER_ID in runtime._wait_for_qa_runner(client, token, runner_id=LOCAL_RUNNER_ID)

    def api(method, path, **kwargs):
        response = client.request(method, '/api/v1/' + path, **kwargs).json()
        assert response['code'] == 0, response
        return response['data']

    api('PUT', 'workspaces/current/language', json={'language': 'zh_Hans'})
    url, records = provider_wire
    provider = api(
        'POST',
        'provider/providers',
        json={'name': 'QA', 'requester': 'openai-chat-completions', 'base_url': url, 'api_keys': ['fake-key']},
    )['uuid']
    primary, _ = [
        api('POST', 'provider/models/llm', json={'name': name, 'provider_uuid': provider, 'abilities': []})['uuid']
        for name in ('mock-a', 'mock-b')
    ]
    pipeline = api('POST', 'pipelines', json={'name': 'LocalAgent QA'})['uuid']
    config = api('GET', f'pipelines/{pipeline}')['pipeline']['config']
    config['ai'].update(
        runner={'id': LOCAL_RUNNER_ID}, runner_config={LOCAL_RUNNER_ID: {'model': {'primary': primary}}}
    )
    api('PUT', f'pipelines/{pipeline}', json={'config': config})
    bot = api(
        'POST',
        'platform/bots',
        json={
            'name': 'QA',
            'enable': True,
            'adapter': 'http_bot',
            'adapter_config': {'signature_required': True, 'inbound_secret': 'qa-signer', 'callback_timeout': 10},
            'command_settings': {'builtin': {'model': {'enabled': True}}},
            'event_bindings': [
                {'event_pattern': 'message.received', 'target_type': 'pipeline', 'target_uuid': pipeline}
            ],
        },
    )['uuid']

    api('POST', f'platform/bots/{bot}/admins', json={'launcher_type': 'person', 'launcher_id': 'admin'})

    def send(text, sender='admin'):
        body = json.dumps(
            {'session_id': sender, 'session_type': 'person', 'message': [{'type': 'Plain', 'text': text}]}
        ).encode()
        result = client.post(
            f'/bots/{bot}/sync',
            content=body,
            headers=signed_headers(body, 'qa-signer'),
        ).json()
        assert result['code'] == 0, result
        return ''.join(part['text'] for part in result['data']['message'] if part.get('type') == 'Plain')

    def chat(text, model, sender='admin'):
        assert 'hello world' in send(text, sender)
        assert records[-1]['body']['model'] == model

    chat('first turn', 'mock-a')
    assert send('/model mock-b') == '已切换为 mock-b（仅当前会话）'
    chat('second turn', 'mock-b')
    count = len(records)
    assert '正在重新生成' in send('/retry')
    deadline = time.monotonic() + 20
    while len(records) == count and time.monotonic() < deadline:
        time.sleep(0.1)
    assert len(records) == count + 1
    body = records[-1]['body']
    assert body['model'] == 'mock-b'
    assert 'second turn' in str([msg for msg in body['messages'] if msg['role'] == 'user'][-1]['content'])
    chat('other session', 'mock-a', 'other')
    assert '已开始新会话' in send('/new')
    chat('after reset', 'mock-a')
