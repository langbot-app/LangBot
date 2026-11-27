import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
import yaml

from tests.e2e import test_runner_plugin_runtime as runtime
from tools.regression.http_bot import signed_headers


@pytest.mark.e2e
@pytest.mark.parametrize('enabled', [True, False])
def test_command_telemetry_at_local_receiver(tmp_path, enabled):
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/api/v1/telemetry':
                received.append(payload)
            reply = json.dumps({'code': 0, 'data': {'stored': len(payload.get('records', [])), 'rejected': 0}}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    with ThreadingHTTPServer(('127.0.0.1', 0), Receiver) as receiver:
        port = runtime._free_port()
        config = runtime.create_minimal_config(tmp_path, port)
        runtime.create_test_directories(tmp_path)
        settings = yaml.safe_load(config.read_text())
        settings['space'].update(
            url=f'http://127.0.0.1:{receiver.server_port}', execution_trace_sample=1, telemetry_flush_seconds=1
        )
        config.write_text(yaml.safe_dump(settings))
        server = threading.Thread(target=receiver.serve_forever)
        server.start()
        proc = runtime.LangBotProcess(
            runtime.find_project_root(),
            tmp_path,
            port=port,
            timeout=360,
            collect_coverage=False,
            cli_args=['--standalone-runtime'],
            telemetry_port=receiver.server_port if enabled else None,
        )
        try:
            assert proc.start()
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as client:
                token = runtime._init_and_auth(client)
                created = client.post(
                    '/api/v1/platform/bots',
                    headers={'Authorization': f'Bearer {token}'},
                    json={
                        'adapter': 'http_bot',
                        'name': 'telemetry',
                        'enable': True,
                        'adapter_config': {'inbound_secret': 'qa-signer', 'callback_timeout': 2},
                    },
                ).json()
                assert created['code'] == 0, created
                bot = created['data']['uuid']
                for command in ('/whoami', '/status'):
                    body = json.dumps(
                        {'session_type': 'person', 'session_id': 'qa', 'message': [{'type': 'Plain', 'text': command}]}
                    ).encode()
                    reply = client.post(
                        f'/bots/{bot}/sync', content=body, headers=signed_headers(body, 'qa-signer')
                    ).json()
                    assert reply['code'] == 0, reply
                    assert bool(reply['data']['message']) == (command == '/whoami')
                deadline = time.monotonic() + (75 if enabled else 35)
                while time.monotonic() < deadline:
                    if any(payload.get('event_type') == 'instance_heartbeat' for payload in received):
                        break
                    time.sleep(0.25)
        finally:
            proc.stop()
            receiver.shutdown()
            server.join()
    if not enabled:
        assert not received
        return
    commands = {
        (node['operation'], node['outcome'])
        for payload in received
        for node in payload.get('records', [])
        if node.get('event_type') == 'execution_node' and node.get('family') == 'command'
    }
    assert {('builtin:whoami', 'ok'), ('builtin:status', 'denied')} <= commands
    features = next(payload['features'] for payload in received if payload.get('event_type') == 'instance_heartbeat')
    assert features['commands_disabled_bots'] == 0
    outcomes = {
        (dims['name'], dims['outcome'])
        for metric, dims, count in features['usage']['c']
        if metric == 'command.run' and count == 1
    }
    assert outcomes == {('whoami', 'ok'), ('status', 'denied')}
