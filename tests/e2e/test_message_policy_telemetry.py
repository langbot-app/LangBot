import json
import sqlite3
from contextlib import ExitStack, closing, contextmanager
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

    with ThreadingHTTPServer(('127.0.0.1', 0), Receiver) as receiver, ExitStack() as services:
        port = runtime._free_port()
        if enabled:
            ports = runtime.runner_runtime_ports.__wrapped__()
            config = runtime.runner_e2e_config_path.__wrapped__(tmp_path, port, ports)
            services.enter_context(contextmanager(runtime.runner_runtime_process.__wrapped__)(tmp_path, ports))
        else:
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
            env_overrides={'LANGBOT_TELEMETRY_HEARTBEAT_SECONDS': '30'},
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
                if enabled:
                    _check_route_access_policy(client, token, bot, tmp_path)
                    runtime._ensure_qa_plugin(client, token, tmp_path / 'agent-runner-qa.zip')
                    agent_events, completed_events = _check_agent_ingress(client, token, bot, tmp_path)
                    hook_events, command_hooks = _check_hook_intercepts(client, token, bot, tmp_path)
                else:
                    unavailable = client.post(
                        '/api/v1/agents',
                        headers={'Authorization': 'Bearer ' + token},
                        json={
                            'name': 'Missing Runner',
                            'kind': 'agent',
                            'supported_event_patterns': ['message.*'],
                            'config': {
                                'runner': {'id': runtime.QA_RUNNER_ID},
                                'runner_config': {runtime.QA_RUNNER_ID: {}},
                            },
                        },
                    )
                    assert unavailable.status_code == 400 and runtime.QA_RUNNER_ID in unavailable.json()['msg']
                deadline = time.monotonic() + (75 if enabled else 35)
                while time.monotonic() < deadline:
                    if any(payload.get('event_type') == 'instance_heartbeat' for payload in received) and (
                        not enabled
                        or (
                            _access_layers(received) == {'bot', 'route'}
                            and agent_events <= _agent_drops(received)
                            and completed_events <= _successful_runs(received)
                            and _long_text_usage(received) >= 4
                            and _hook_usage(received)
                            == {'MessageReceived': 2, 'NormalMessageReceived': 2, 'CommandSent': 2}
                            and hook_events <= _successful_event_routes(received)
                        )
                    ):
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
    assert _access_layers(received) == {'bot', 'route'}
    assert agent_events <= _agent_drops(received)
    assert completed_events <= _successful_runs(received)
    assert _long_text_usage(received) == 4
    assert _hook_usage(received) == {'MessageReceived': 2, 'NormalMessageReceived': 2, 'CommandSent': 2}
    for event_id in hook_events:
        nodes = [
            node
            for payload in received
            for node in payload.get('records', [])
            if node.get('event_type') == 'execution_node' and node.get('event_id') == event_id
        ]
        assert any(node['family'] == 'event_route' and node['outcome'] == 'success' for node in nodes), nodes
        assert not any(node['family'] == 'runner' for node in nodes), nodes
        if event_id in command_hooks:
            assert [(n['operation'], n['outcome']) for n in nodes if n['family'] == 'command'] == [
                ('builtin:whoami', 'intercepted')
            ], nodes
    assert not any(
        node.get('family') == 'runner' and node.get('event_id') in agent_events
        for payload in received
        for node in payload.get('records', [])
    )
    outcomes = {
        (dims['name'], dims['outcome'])
        for payload in received
        if payload.get('event_type') == 'instance_heartbeat'
        for metric, dims, count in payload['features']['usage']['c']
        if metric == 'command.run' and count >= 1
    }
    assert outcomes == {('whoami', 'ok'), ('status', 'denied'), ('whoami', 'intercepted')}


def _access_layers(received):
    return {
        node['layer']
        for payload in received
        for node in payload.get('records', [])
        if node.get('family') == 'message_policy'
        and node.get('operation') == 'access-control'
        and node.get('outcome') == 'discarded'
    }


def _hook_usage(received):
    counts = {}
    for payload in received:
        if payload.get('event_type') == 'instance_heartbeat':
            for metric, dims, count in payload['features']['usage']['c']:
                if metric == 'hook.intercept':
                    name = dims['event']
                    counts[name] = counts.get(name, 0) + count
    return counts


def _successful_event_routes(received):
    return {
        node['event_id']
        for payload in received
        for node in payload.get('records', [])
        if (node.get('event_type'), node.get('family'), node.get('outcome'))
        == ('execution_node', 'event_route', 'success')
    }


def _check_hook_intercepts(client, token, bot, tmp_path):
    headers = {'Authorization': 'Bearer ' + token}
    url = '/api/v1/platform/bots/' + bot
    route = client.get(url, headers=headers).json()['data']['bot']['event_bindings'][0]
    route['policy'] = {
        'plugins': {'enable_all': False, 'plugins': [{'author': 'e2e', 'name': 'agent-runner-qa'}]},
        'output': {'misc': {'at-sender': False}},
    }
    saved = client.put(url, headers=headers, json={'event_bindings': [route]}).json()
    assert saved['code'] == 0, saved
    ids = set()
    command_hooks = set()
    for kind in ('person', 'group'):
        for hook in ('MessageReceived', 'NormalMessageReceived', 'CommandSent'):
            name = kind.title() + hook
            text = f'/whoami hook-probe {kind}' if hook == 'CommandSent' else 'trace-hook:' + name
            body = json.dumps(
                {'session_type': kind, 'session_id': 'agent', 'message': [{'type': 'Plain', 'text': text}]}
            ).encode()
            reply = client.post(
                '/bots/' + bot + '/sync', content=body, headers=signed_headers(body, 'qa-signer')
            ).json()
            assert reply['code'] == 0, reply
            sequence = [name] if hook == 'MessageReceived' else [kind.title() + 'MessageReceived', name]
            expected = name + ':1' if hook == 'CommandSent' else ' > '.join(sequence)
            assert reply['data']['message'] == [{'type': 'Plain', 'text': expected}], reply
            event_id = f'platform:{bot}:{reply["data"]["reply_to"]}'
            with closing(sqlite3.connect(tmp_path / 'data/langbot.db')) as db:
                row = db.execute(
                    'SELECT metadata_json FROM event_log WHERE event_id=? AND bot_id=?', (event_id, bot)
                ).fetchone()
                assert db.execute('SELECT count(*) FROM agent_run WHERE event_id=?', (event_id,)).fetchone() == (0,)
            metadata = json.loads(row[0])
            (primary,) = metadata['routes']
            assert (metadata['status'], primary['target_type'], primary['status'], primary['hook']) == (
                'completed',
                'plugin',
                'delivered',
                hook,
            ), metadata
            if hook == 'CommandSent':
                detail = client.get('/api/v1/monitoring/executions/event/' + event_id, headers=headers).json()
                assert detail['code'] == 0, detail
                row = detail['data']['row']
                assert (row['event_id'], row['handling'], row['handled_by'], row['hook']) == (
                    event_id,
                    'plugin',
                    'plugin:e2e/agent-runner-qa',
                    hook,
                ), row
                assert primary['reason'] == f'{name} handled by {row["handled_by"]}', primary
                assert detail['data']['counts']['events'] == 0
                command_hooks.add(event_id)
            ids.add(event_id)
    assert len(ids) == 6 and len(command_hooks) == 2
    return ids, command_hooks


def _agent_drops(received):
    return {
        node['event_id']
        for payload in received
        for node in payload.get('records', [])
        if (node.get('family'), node.get('operation'), node.get('outcome'), node.get('layer'))
        == ('message_policy', 'ignore-rules', 'discarded', 'route')
    }


def _successful_runs(received):
    return {
        node['event_id']
        for payload in received
        for node in payload.get('records', [])
        if (node.get('family'), node.get('operation'), node.get('mode'), node.get('outcome'))
        == ('runner', 'execute', 'agent', 'success')
    }


def _long_text_usage(received):
    return sum(
        count
        for payload in received
        if payload.get('event_type') == 'instance_heartbeat'
        for metric, dims, count in payload['features']['usage']['c']
        if metric == 'output.transform' and dims == {'kind': 'long_text'}
    )


def _check_agent_ingress(client, token, bot, tmp_path):
    headers = {'Authorization': 'Bearer ' + token}
    agent = client.post(
        '/api/v1/agents',
        headers=headers,
        json={
            'kind': 'agent',
            'name': 'Admission QA',
            'supported_event_patterns': ['message.*'],
            'config': {'runner': {'id': runtime.QA_RUNNER_ID}, 'runner_config': {runtime.QA_RUNNER_ID: {}}},
        },
    ).json()
    assert agent['code'] == 0, agent
    target = agent['data']['uuid']
    updated = client.put(
        '/api/v1/platform/bots/' + bot,
        headers=headers,
        json={
            'event_bindings': [
                {
                    'id': 'agent',
                    'event_pattern': 'message.received',
                    'target_type': 'agent',
                    'target_uuid': target,
                    'policy': {
                        'trigger': {'ignore-rules': {'prefix': ['ignored:']}},
                        'output': {
                            'long-text-processing': {'threshold': 32, 'strategy': 'forward'},
                            'misc': {'at-sender': False},
                        },
                    },
                }
            ],
        },
    ).json()
    assert updated['code'] == 0, updated
    event_ids = set()
    completed_events = set()
    for kind in ('person', 'group'):
        body = json.dumps(
            {'session_type': kind, 'session_id': 'agent', 'message': [{'type': 'Plain', 'text': 'ignored: QA'}]}
        ).encode()
        reply = client.post('/bots/' + bot + '/sync', content=body, headers=signed_headers(body, 'qa-signer')).json()
        assert reply['code'] == 0 and not reply['data']['message'], reply
        event_id = f'platform:{bot}:{reply["data"]["reply_to"]}'
        with closing(sqlite3.connect(tmp_path / 'data/langbot.db')) as db:
            row = db.execute(
                'SELECT metadata_json FROM event_log WHERE bot_id=? AND event_id=?', (bot, event_id)
            ).fetchone()
        metadata = json.loads(row[0])
        (route,) = metadata['routes']
        assert (
            metadata['status'],
            route['target_type'],
            route['target_uuid'],
            route['policy_item'],
            route['policy_layer'],
        ) == ('ignored', 'agent', target, 'ignore-rules', 'route'), metadata
        event_ids.add(event_id)
        for length in (31, 32, 33, 32768):
            prefix = 'e2e echo: '
            text = '界' * (length - len(prefix))
            body = json.dumps(
                {'session_type': kind, 'session_id': 'agent', 'message': [{'type': 'Plain', 'text': text}]}
            ).encode()
            reply = client.post(
                '/bots/' + bot + '/sync', content=body, headers=signed_headers(body, 'qa-signer')
            ).json()
            assert reply['code'] == 0, reply
            (part,) = reply['data']['message']
            if length > 32:
                assert part['type'] == 'Forward'
                (node,) = part['node_list']
                (part,) = node['message_chain']
            assert part['type'] == 'Plain' and part['text'] == prefix + text
            event_id = f'platform:{bot}:{reply["data"]["reply_to"]}'
            with closing(sqlite3.connect(tmp_path / 'data/langbot.db')) as db:
                row = db.execute(
                    'SELECT metadata_json FROM event_log WHERE bot_id=? AND event_id=?', (bot, event_id)
                ).fetchone()
            metadata = json.loads(row[0])
            (route,) = metadata['routes']
            assert (route['target_uuid'], route['target_type'], route['status']) == (target, 'agent', 'delivered'), (
                metadata
            )
            transforms = [
                action
                for event in metadata.get('policy_events', [])
                for action in event.get('actions', [])
                if action['kind'] == 'long_text'
            ]
            assert transforms == ([{'kind': 'long_text', 'strategy': 'forward'}] if length > 32 else [])
            completed_events.add(event_id)
    assert len(completed_events) == 8
    return event_ids, completed_events


def _check_route_access_policy(client, token, bot, tmp_path):
    headers = {'Authorization': 'Bearer ' + token}
    bot_path = '/api/v1/platform/bots/' + bot

    def api(method, path, **kwargs):
        result = client.request(method, path, headers=headers, **kwargs).json()
        assert result['code'] == 0, result
        return result['data']

    chat = api('POST', '/api/v1/pipelines', json={'name': 'Route QA'})['uuid']
    route = {'id': 'access', 'event_pattern': 'message.received', 'target_type': 'pipeline', 'target_uuid': chat}
    bot_policy = {
        'trigger': {
            'access-control': {'mode': 'blacklist', 'blacklist': ['person_blocked', 'group_blocked']},
            'group-respond-rules': {'enabled': False},
        }
    }
    override = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': ['person_blocked', 'group_blocked']}}}
    api('PUT', bot_path, json={'message_policy': bot_policy, 'event_bindings': [{**route, 'policy': override}]})
    api('PUT', bot_path, json={'event_bindings': [route]})
    assert api('GET', bot_path)['bot']['event_bindings'][0]['policy'] == override
    for layer in ('route', 'bot'):
        if layer == 'bot':
            api('PUT', bot_path, json={'event_bindings': [{**route, 'policy': None}]})
            assert 'policy' not in api('GET', bot_path)['bot']['event_bindings'][0]
        for kind in ('person', 'group'):
            for session in ('allowed', 'blocked'):
                allowed = (layer == 'bot') == (session == 'allowed')
                body = json.dumps(
                    {'session_type': kind, 'session_id': session, 'message': [{'type': 'Plain', 'text': '/whoami'}]}
                ).encode()
                reply = client.post(
                    '/bots/' + bot + '/sync', content=body, headers=signed_headers(body, 'qa-signer')
                ).json()
                assert reply['code'] == 0 and bool(reply['data']['message']) == allowed, (layer, kind, session, reply)
                if not allowed:
                    with closing(sqlite3.connect(tmp_path / 'data/langbot.db')) as db:
                        row = db.execute(
                            "SELECT metadata_json FROM event_log WHERE bot_id=? AND event_type='message.received' ORDER BY id DESC LIMIT 1",
                            (bot,),
                        ).fetchone()
                    metadata = json.loads(row[0])
                    (primary,) = metadata['routes']
                    assert (metadata['status'], primary['policy_layer'], primary['policy_item']) == (
                        'ignored',
                        layer,
                        'access-control',
                    ), metadata
