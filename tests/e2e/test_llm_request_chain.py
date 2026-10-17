"""Real HTTP -> Core -> Plugin Runtime -> Runner -> Core -> HTTP provider tests.

Only the remote provider is deterministic. No requester, SDK action transport,
model manager, persistence or monitoring implementation is mocked.
"""

import json
import importlib.metadata
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import select
import socket
import sqlite3
import threading
import time

import pytest
import yaml
import httpx
from packaging.version import Version

from tests.e2e import test_runner_plugin_runtime as runtime

# Reuse the real process lifecycle; override the package/config and port below.
runner_runtime_ports = runtime.runner_runtime_ports
runner_runtime_process = runtime.runner_runtime_process
runner_langbot_process = runtime.runner_langbot_process
runner_client = runtime.runner_client

pytestmark = pytest.mark.e2e
RUNNER = runtime.QA_RUNNER_ID
USAGE = {
    'prompt_tokens': 24,
    'completion_tokens': 4,
    'total_tokens': 28,
    'prompt_tokens_details': {'cached_tokens': 16},
    'completion_tokens_details': {'reasoning_tokens': 2},
}


@pytest.fixture(scope='session')
def runner_e2e_tmpdir(tmp_path_factory):
    # Retain logs/SQLite in pytest's bounded temp history for failure diagnosis.
    return tmp_path_factory.mktemp('llm-chain')


@pytest.fixture(scope='session')
def runner_e2e_port():
    return runtime._free_port()


@pytest.fixture(scope='session')
def runner_e2e_config_path(runner_e2e_tmpdir, runner_e2e_port, runner_runtime_ports):
    path = runtime.runner_e2e_config_path.__wrapped__(runner_e2e_tmpdir, runner_e2e_port, runner_runtime_ports)
    root = runner_e2e_tmpdir / 'agent-runner-qa-package'
    manifest = root / 'components/runner/default.yaml'
    data = yaml.safe_load(manifest.read_text(encoding='utf-8'))
    data['spec']['permissions'] = {'models': ['invoke', 'stream', 'count_tokens']}
    data['spec']['config'] = [
        {'name': 'model', 'label': {'en_US': 'Model'}, 'type': 'llm-model-selector', 'required': True},
    ]
    manifest.write_text(yaml.safe_dump(data), encoding='utf-8')
    shutil.copyfile(Path(__file__).parent / 'utils/llm_probe_runner.py', root / 'components/runner/default.py')
    if legacy_root := os.environ.get('LLM_E2E_LEGACY_API_DIR'):
        for filename in ('legacy_api.py', 'legacy_message.py'):
            shutil.copyfile(Path(legacy_root) / filename, root / filename)
    shutil.make_archive(str(runner_e2e_tmpdir / 'agent-runner-qa'), 'zip', root_dir=root)
    return path


@pytest.fixture(scope='module')
def provider_wire():
    records = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            scenario = self.headers.get('x-e2e-case', 'normal')
            row = {'body': body, 'headers': dict(self.headers), 'case': scenario, 'closed': False}
            records.append(row)
            attempt = sum(x['case'] == scenario for x in records)
            status = 503 if scenario.startswith('retry') and attempt == 1 else 200
            if scenario == 'auth':
                status = 401
            if status != 200:
                data = json.dumps({'error': {'message': 'injected failure', 'type': 'api_error'}}).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Retry-After', '0')
                self.end_headers()
                self.wfile.write(data)
                return
            if scenario in ('first-timeout', 'total-timeout'):
                time.sleep(1)
            try:
                if not body.get('stream'):
                    data = json.dumps(
                        {
                            'id': 'e2e',
                            'object': 'chat.completion',
                            'created': 1,
                            'model': body['model'],
                            'choices': [
                                {
                                    'index': 0,
                                    'message': {'role': 'assistant', 'content': 'hello world'},
                                    'finish_reason': 'stop',
                                }
                            ],
                            'usage': USAGE,
                        }
                    ).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()

                def send(event):
                    data = ('data: ' + (event if isinstance(event, str) else json.dumps(event)) + '\n\n').encode()
                    self.wfile.write(f'{len(data):X}\r\n'.encode() + data + b'\r\n')
                    self.wfile.flush()

                base = {'id': 'e2e', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model']}
                if scenario.startswith('reasoning-'):
                    send(
                        {
                            **base,
                            'choices': [
                                {'index': 0, 'delta': {'reasoning_content': 'private thought'}, 'finish_reason': None}
                            ],
                        }
                    )
                for index, content in enumerate(['hello ', 'world']):
                    send({**base, 'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]})
                    if index == 0 and (scenario in ('idle-timeout', 'disconnect') or scenario.startswith('cancel-')):
                        if scenario == 'disconnect':
                            self.close_connection = True
                            return
                        deadline = time.monotonic() + 1
                        while time.monotonic() < deadline:
                            if select.select([self.connection], [], [], 0.02)[0]:
                                if not self.connection.recv(1, socket.MSG_PEEK):
                                    row['closed'] = True
                                    return
                send({**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})
                send({**base, 'choices': [], 'usage': USAGE})
                send('[DONE]')
                self.wfile.write(b'0\r\n\r\n')
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                row['closed'] = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/v1', records
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture(scope='module')
def chain(request, provider_wire):
    request.getfixturevalue('runner_langbot_process')
    port = request.getfixturevalue('runner_e2e_port')
    client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=90, trust_env=False)
    request.addfinalizer(client.close)
    tmpdir = request.getfixturevalue('runner_e2e_tmpdir')
    token = runtime._init_and_auth(client)
    runtime._ensure_qa_plugin(client, token, tmpdir / 'agent-runner-qa.zip')
    client.headers['Authorization'] = f'Bearer {token}'

    def post(path, body):
        response = client.post('/api/v1/' + path, json=body)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['code'] == 0, payload
        return payload['data']

    provider = post(
        'provider/providers',
        {
            'name': 'LLM chain E2E',
            'requester': 'openai-chat-completions',
            'base_url': provider_wire[0],
            'api_keys': ['e2e-not-a-secret'],
        },
    )['uuid']
    model = post(
        'provider/models/llm',
        {
            'name': 'gpt-4o',
            'provider_uuid': provider,
            'abilities': ['func_call', 'vision'],
            'extra_args': {
                'temperature': 0.1,
                'request_policy': {'retries': 1, 'backoff_base': 0.01, 'backoff_max': 0.01},
            },
        },
    )['uuid']
    agent = post(
        'agents',
        {
            'kind': 'agent',
            'name': 'LLM chain E2E',
            'config': {
                'runner': {'id': RUNNER},
                'runner_config': {RUNNER: {'model': model}},
            },
        },
    )['uuid']

    def invoke(mode, case='normal', extra=None, *, configuration=None, options=None):
        selected_model, selected_agent = model, agent
        if configuration:
            configured_provider = post(
                'provider/providers',
                {
                    'name': case,
                    'requester': configuration.get('requester', 'openai-chat-completions'),
                    'base_url': provider_wire[0],
                    'api_keys': ['e2e-not-a-secret'],
                },
            )['uuid']
            selected_model = post(
                'provider/models/llm',
                {
                    'name': configuration.get('name', 'gpt-4o'),
                    'provider_uuid': configured_provider,
                    'abilities': ['func_call', 'vision'],
                    'extra_args': configuration.get('extra_args', {}),
                },
            )['uuid']
            selected_agent = post(
                'agents',
                {
                    'kind': 'agent',
                    'name': case,
                    'config': {
                        'runner': {'id': RUNNER},
                        'runner_config': {RUNNER: {'model': selected_model}},
                    },
                },
            )['uuid']
        result = post(
            f'agents/{selected_agent}/debug',
            {
                'text': json.dumps(
                    {'mode': mode, 'model': selected_model, 'case': case, 'extra': extra or {}, **(options or {})}
                ),
                'conversation_id': 'e2e-' + case,
                'event_type': 'message.received',
            },
        )
        assert result.get('final_text'), result
        return json.loads(result['final_text'])

    return invoke, provider_wire[1], tmpdir


def test_multimodal_and_tool_definitions_survive_plugin_transport(chain):
    invoke, records, _ = chain
    image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
    messages = [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'Describe this image'},
                {'type': 'image_url', 'image_url': {'url': image}},
            ],
        }
    ]
    result = invoke('runner-events', 'multimodal', options={'messages': messages, 'tool': True})
    assert result['text'] == 'hello world', result
    wire = records[-1]['body']
    assert wire['messages'][0]['content'][1]['image_url']['url'] == image
    assert wire['tools'][0]['function']['name'] == 'e2e_lookup'


def test_openrouter_budget_cache_and_explicit_attribution(chain):
    invoke, records, _ = chain
    result = invoke(
        'runner-events',
        'openrouter-budget-cache',
        configuration={
            'requester': 'openrouter-chat-completions',
            'name': 'anthropic/claude-sonnet-4',
            'extra_args': {
                'reasoning_config': {'budget_tokens': 2048},
                'prompt_caching': {'mode': 'anthropic'},
                'max_tokens': 4096,
            },
        },
        extra={
            'extra_headers': {'HTTP-Referer': 'https://langbot.app', 'X-OpenRouter-Title': 'LangBot'},
            'request_policy': {'conversation_header': 'x-langbot-conversation-id'},
        },
        options={'messages': [{'role': 'system', 'content': 'Stable prefix'}, {'role': 'user', 'content': 'Hello'}]},
    )
    assert result['text'] == 'hello world', result
    wire = records[-1]
    assert wire['body']['reasoning']['max_tokens'] == 2048
    assert wire['body']['messages'][0]['content'][0]['cache_control']['type'] == 'ephemeral'
    headers = {k.lower(): v for k, v in wire['headers'].items()}
    assert headers['http-referer'] == 'https://langbot.app'
    assert headers['x-openrouter-title'] == 'LangBot'
    assert headers['x-langbot-conversation-id'].startswith('lb-')
    assert 'prompt_caching' not in wire['body'] and 'reasoning_config' not in wire['body']


def test_openai_cache_options_and_call_override(chain):
    invoke, records, _ = chain
    result = invoke(
        'runner-usage',
        'openai-cache',
        configuration={
            'extra_args': {'temperature': 0.1, 'prompt_caching': {'mode': 'openai', 'retention': 'in_memory'}},
        },
        extra={'temperature': 0.7, 'prompt_cache_key': 'explicit-test-cache'},
    )
    assert result['text'] == 'hello world', result
    assert records[-1]['body']['temperature'] == 0.7
    assert records[-1]['body']['prompt_cache_key'] == 'explicit-test-cache'
    assert records[-1]['body']['prompt_cache_retention'] == 'in_memory'


@pytest.mark.parametrize(
    'mode',
    [
        'runner-message',
        'runner-usage',
        'runner-stream',
        'runner-events',
        'plugin-message',
        'plugin-usage',
        'plugin-stream',
        'plugin-events',
    ],
)
def test_public_api_shapes_and_usage(chain, mode):
    invoke, records, _ = chain
    result = invoke(mode, mode)
    assert result['text'] == 'hello world', result
    assert not result.get('error'), result
    if mode.endswith(('usage', 'events')):
        assert result['usage']['prompt_tokens_details']['cached_tokens'] == 16
        assert result['usage']['completion_tokens_details']['reasoning_tokens'] == 2
    wire = records[-1]['body']
    assert wire['temperature'] == 0.1
    assert 'request_policy' not in wire


@pytest.mark.parametrize(
    'case,extra,attempts,error',
    [
        ('retry-once', {}, 2, False),
        ('retry-disabled', {'num_retries': 0}, 1, True),
        ('retry-max-disabled', {'max_retries': 0}, 1, True),
        ('auth', {}, 1, True),
        ('first-timeout', {'request_policy': {'first_event_timeout': 0.2, 'retries': 0}}, 1, True),
        ('total-timeout', {'request_policy': {'total_timeout': 0.2, 'retries': 0}}, 1, True),
        ('idle-timeout', {'request_policy': {'stream_idle_timeout': 0.2}}, 1, True),
        ('disconnect', {}, 1, True),
    ],
)
def test_failures_retry_boundaries_and_recovery(chain, case, extra, attempts, error):
    invoke, records, _ = chain
    result = invoke('runner-events', case, extra)
    assert bool(result.get('error')) == error, result
    assert sum(row['case'] == case for row in records) == attempts
    assert invoke('runner-events', 'recover-' + case)['text'] == 'hello world'


@pytest.mark.parametrize('surface', ['runner-events', 'runner-stream', 'plugin-events', 'plugin-stream'])
def test_cancellation_releases_upstream_and_next_request_works(chain, surface):
    invoke, records, tmpdir = chain
    case = 'cancel-' + surface
    result = invoke(case, case)
    assert result['text'] == 'hello ', result
    time.sleep(1.5)
    cancelled = [row for row in records if row['case'] == case]
    with sqlite3.connect(tmpdir / 'data/langbot.db') as db:
        diagnostics = db.execute('SELECT session_id, details FROM monitoring_llm_calls').fetchall()
    assert len(cancelled) == 1
    assert invoke('runner-events', 'after-' + case)['text'] == 'hello world'
    if (
        not cancelled[0]['closed']
        and Version(importlib.metadata.version('langbot-plugin')) <= Version('0.7.11')
        and not os.environ.get('LLM_E2E_REQUIRE_STREAM_CLOSE')
    ):
        pytest.xfail('Published SDK <=0.7.11 omits aclosing in public proxy wrappers; requires companion SDK fix')
    assert cancelled[0]['closed'], diagnostics[-2:]


@pytest.mark.parametrize('remove_think', [True, False])
def test_reasoning_visibility_through_runner(chain, remove_think):
    result = chain[0]('runner-events', f'reasoning-{remove_think}', options={'remove_think': remove_think})
    assert result['text'].endswith('hello world'), result
    assert ('private thought' in result['text']) == (not remove_think)


def test_invalid_budget_fails_before_network_and_recovers(chain):
    invoke, records, _ = chain
    result = invoke('runner-events', 'invalid-budget', {'reasoning_config': {'budget_tokens': 1}})
    assert result.get('error'), result
    assert not any(row['case'] == 'invalid-budget' for row in records)
    assert invoke('runner-events', 'after-invalid-budget')['text'] == 'hello world'


def test_monitoring_persists_complete_usage_and_structured_errors(chain):
    invoke, _, tmpdir = chain
    invoke('runner-events', 'monitoring')
    with sqlite3.connect(tmpdir / 'data/langbot.db') as db:
        rows = db.execute('SELECT details FROM monitoring_llm_calls').fetchall()
    details = [json.loads(row[0]) for row in rows if row[0]]
    assert any(x.get('usage', {}).get('prompt_tokens_details', {}).get('cached_tokens') == 16 for x in details)
    assert any(x.get('timing', {}).get('transport_setup_ms') is not None for x in details)
    assert any(x.get('error', {}).get('code') for x in details if x.get('error'))


@pytest.mark.skipif(not os.environ.get('LLM_E2E_LEGACY_API_DIR'), reason='Historical SDK sources not supplied')
@pytest.mark.parametrize('mode', ['legacy-message', 'legacy-usage', 'legacy-stream', 'legacy-events'])
def test_historical_sdk_proxy_and_message_entities(chain, mode):
    result = chain[0](mode, mode)
    assert result['text'] == 'hello world', result
    assert not result.get('error'), result
    if mode.endswith(('usage', 'events')):
        assert result['usage']['prompt_tokens_details']['cached_tokens'] == 16
