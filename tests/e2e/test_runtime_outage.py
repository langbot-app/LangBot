import contextlib
import json
import socket
import sqlite3
import tempfile
import time
from pathlib import Path

import httpx
import pytest
import yaml

from tests.e2e import test_runner_plugin_runtime as runtime
from tools.regression.http_bot import signed_headers


@pytest.mark.e2e
def test_builtin_commands_across_runtime_outage():
    root = runtime.find_project_root()
    scratch = root / '.qa'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        work = Path(directory)
        port = runtime._free_port()
        ports = runtime.runner_runtime_ports.__wrapped__()
        path = runtime.runner_e2e_config_path.__wrapped__(work, port, ports)
        config = yaml.safe_load(path.read_text())
        config['plugin']['connect_timeout_seconds'] = 3
        path.write_text(yaml.safe_dump(config))
        core = runtime.LangBotProcess(
            root, work, port=port, timeout=360, collect_coverage=False, cli_args=['--standalone-runtime']
        )
        try:
            assert core.start()
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False) as client:
                token = runtime._init_and_auth(client)
                headers = {'Authorization': 'Bearer ' + token}
                created = client.post(
                    '/api/v1/platform/bots',
                    headers=headers,
                    json={
                        'name': 'Offline QA',
                        'adapter': 'http_bot',
                        'enable': True,
                        'adapter_config': {
                            'signature_required': True,
                            'inbound_secret': 'qa-sign',
                            'callback_timeout': 2,
                        },
                        'message_policy': {'trigger': {'group-respond-rules': {'enabled': False}}},
                    },
                ).json()
                assert created['code'] == 0, created
                bot = created['data']['uuid']

                def send(text, kind):
                    body = json.dumps(
                        {'session_type': kind, 'session_id': 'offline', 'message': [{'type': 'Plain', 'text': text}]}
                    ).encode()
                    result = client.post(
                        '/bots/' + bot + '/sync', content=body, headers=signed_headers(body, 'qa-sign')
                    ).json()
                    assert result['code'] == 0, result
                    return [part['text'] for part in result['data']['message'] if part['type'] == 'Plain']

                def check_offline():
                    with socket.socket() as probe:
                        assert probe.connect_ex(('127.0.0.1', ports[0])) != 0
                    select_plugins(True)
                    assert send('/whoami', 'person') == []
                    with contextlib.closing(sqlite3.connect(work / 'data/langbot.db')) as database:
                        row = database.execute(
                            'SELECT metadata_json FROM event_log WHERE bot_id=? AND event_type=? ORDER BY id DESC LIMIT 1',
                            (bot, 'message.received'),
                        ).fetchone()
                    metadata = json.loads(row[0])
                    assert metadata['status'] == 'failed' and 'runtime' in str(metadata['routes']).lower(), metadata
                    select_plugins(False)
                    for kind in ('person', 'group'):
                        assert 'offline' in ' '.join(send('/whoami', kind))
                        assert send('/status', kind) == []

                def select_plugins(all_enabled):
                    result = client.put(
                        '/api/v1/platform/bots/' + bot,
                        headers=headers,
                        json={
                            'message_policy': {
                                'plugins': {'enable_all': all_enabled, 'plugins': []},
                                'trigger': {'group-respond-rules': {'enabled': False}},
                            }
                        },
                    ).json()
                    assert result['code'] == 0, result

                def wait_connected():
                    deadline = time.monotonic() + 60
                    while True:
                        status = client.get('/api/v1/system/status/plugin-system', headers=headers).json()
                        if status['code'] == 0 and status['data']['is_connected']:
                            break
                        assert time.monotonic() < deadline, status
                        time.sleep(0.5)

                check_offline()
                start_runtime = contextlib.contextmanager(runtime.runner_runtime_process.__wrapped__)
                with start_runtime(work, ports):
                    wait_connected()
                    select_plugins(True)
                    runtime._ensure_qa_plugin(client, token, work / 'agent-runner-qa.zip')
                    assert send('/qa_boundary_command query-probe', 'person') == ['command:' + bot]
                check_offline()
                with start_runtime(work, ports):
                    wait_connected()
                    select_plugins(True)
                    assert runtime.QA_RUNNER_ID in runtime._wait_for_qa_runner(client, token)
                    assert send('/qa_boundary_command query-probe', 'group') == ['command:' + bot]
        finally:
            core.stop()
