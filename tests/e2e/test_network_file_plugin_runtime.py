"""Opt-in TCP HTTP → installed Runner → Box → HTTP file delivery acceptance.

Run on Linux with LANGBOT_NETWORK_PLUGIN_E2E=1 and an in-tree SDK installed.
LANGBOT_CORE_NETWORK_BACKEND selects host (default), nsjail or e2b. The latter
uses E2B_API_KEY/API_URL/SANDBOX_URL/TEMPLATE; nsjail uses the existing delegated
LANGBOT_NSJAIL_CGROUP_V1_PARENT. No test client or dispatcher replacement is used.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import threading
import time
import uuid

import httpx
import pytest
import yaml

from langbot.pkg.platform.sources import http_bot_signing as signing
from tests.e2e import test_runner_plugin_runtime as runtime_tests
from tests.e2e.test_runner_plugin_runtime import (
    QA_RUNNER_ID,
    _ensure_qa_plugin,
    _init_and_auth,
    _wait_for_qa_runner,
    _write_qa_runner_plugin,
)
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.e2e.utils.process_manager import LangBotProcess, find_project_root

runner_client = runtime_tests.runner_client
runner_e2e_port = runtime_tests.runner_e2e_port
runner_runtime_ports = runtime_tests.runner_runtime_ports
runner_runtime_process = runtime_tests.runner_runtime_process

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.network_plugin,
    pytest.mark.contract('registered_runner_file_delivery'),
    pytest.mark.skipif(os.environ.get('LANGBOT_NETWORK_PLUGIN_E2E') != '1', reason='explicit full-process acceptance'),
]

_SECRET = 'network-plugin-e2e-only-secret'
_PERMISSIONS = '/api/v1/plugins/e2e/agent-runner-qa/permissions'


@pytest.fixture(scope='session')
def network_process_env():
    with pytest.MonkeyPatch.context() as patch:
        for name in ('LANGBOT_BOX_CONFIG', 'LANGBOT_BOX_INSTANCE_ID'):
            patch.delenv(name, raising=False)
        yield patch


@pytest.fixture(scope='session')
def runner_e2e_tmpdir(network_process_env):
    # A root-mapped jail cannot traverse another UID's private checkout ancestors.
    root = (
        Path(tempfile.gettempdir())
        if os.environ.get('LANGBOT_CORE_NETWORK_BACKEND') == 'nsjail'
        else find_project_root() / '.qa' / 'network-plugin'
    )
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='full-chain-', dir=root))
    network_process_env.setenv('LANGBOT_PLUGIN_FILE_STORAGE_DIR', str(directory / 'rpc-transfers'))
    yield directory
    if not os.environ.get('LANGBOT_KEEP_RUNNER_E2E'):
        # Runtime seals dependency directories; all processes using this owned tree have stopped.
        for root, _dirs, _files in os.walk(directory):
            os.chmod(root, 0o700)
        shutil.rmtree(directory)


def _write_file_runner(plugin_root):
    _write_qa_runner_plugin(plugin_root)
    manifest_path = plugin_root / 'manifest.yaml'
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest['spec']['components'] = {'Runner': {'fromDirs': [{'path': 'components/runner/'}]}}
    manifest['spec']['permissions'] = {'capabilities': ['sandbox', 'bot.message.send']}
    manifest_path.write_text(yaml.safe_dump(manifest), encoding='utf-8')
    runner_manifest = plugin_root / 'components/runner/default.yaml'
    definition = yaml.safe_load(runner_manifest.read_text())
    definition['spec']['config'] = [
        {'name': name, 'type': 'string', 'label': {'en_US': name}, 'default': '', 'required': False}
        for name in ('reuse_key', 'image')
    ]
    definition['spec']['capabilities']['multimodal_input'] = True
    runner_manifest.write_text(yaml.safe_dump(definition), encoding='utf-8')
    (plugin_root / 'components/runner/default.py').write_text(
        textwrap.dedent("""\
        import json
        import shlex
        from langbot_plugin.api.definition.components.runner.runner import Runner
        from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
        from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

        class DefaultRunner(Runner):
            async def run(self, ctx):
                # Attachment rendering appends references after the leading command.
                request, _ = json.JSONDecoder().raw_decode(ctx.input.to_text().lstrip())
                report = {'run_id': ctx.run_id, 'operation': request['operation']}
                try:
                    if request['operation'] == 'persisted':
                        old = request['run_id']
                        record = await self.plugin.plugin_runtime_handler.call_action(
                            PluginToRuntimeAction.RUN_GET,
                            {'run_id': old, 'target_run_id': old}, 15)
                        report['persisted_run'] = record['run_id']
                        report['persisted_status'] = record['status']
                    elif request['operation'] == 'foreign-ledger':
                        try:
                            await ctx.run_get(request['run_id'])
                        except Exception as error:
                            report['denied'] = str(error)
                    else:
                        status = await ctx.api.get_box_status()
                        box = await ctx.api.acquire_box(
                            status.required_reuse_key or ctx.config['reuse_key'],
                            {'image': ctx.config['image']} if ctx.config['image'] else {})
                        await ctx.bind_box(box.id)
                        report['box_id'] = box.id
                        if request['operation'] == 'foreign-file':
                            try:
                                await ctx.reply_files([request['file_id']])
                            except Exception as error:
                                report['denied'] = str(error)
                        elif request['operation'] == 'revoked':
                            report['unexpected_sandbox_access'] = True
                        else:
                            imported = await ctx.import_box_attachments()
                            assert len(imported) == 1, imported
                            source = imported[0]
                            output = '/tmp/network-plugin-' + ctx.run_id + '.bin'
                            command = ('sha256sum ' + shlex.quote(source.path) +
                                       ' && cp ' + shlex.quote(source.path) + ' ' + shlex.quote(output))
                            result = await ctx.call_tool('exec', {'command': command, 'timeout_sec': 10})
                            assert result['ok'], result
                            exported = await ctx.export_box_files([output])
                            assert len(exported) == 1 and not exported[0].warning, exported
                            check = await ctx.call_tool('exec', {
                                'command': 'test ! -e ' + shlex.quote(output), 'timeout_sec': 5})
                            assert check['ok'], check
                            report.update(file_id=exported[0].id, size=source.size,
                                          sha256=result['stdout'].split()[0])
                            await ctx.reply_files([exported[0].id])
                except Exception as error:
                    report['error'] = str(error)
                await ctx.reply('NETWORK_E2E ' + json.dumps(report))
                yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
        """),
        encoding='utf-8',
    )


@pytest.fixture(scope='session')
def runner_e2e_config_path(runner_e2e_tmpdir, runner_e2e_port, runner_runtime_ports, network_process_env):
    directory = runner_e2e_tmpdir
    backend = os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host')
    assert backend in {'host', 'nsjail', 'e2b'}, 'select one supported backend'
    path = create_minimal_config(directory, port=runner_e2e_port)
    create_test_directories(directory)
    config = yaml.safe_load(path.read_text())
    config['system']['jwt']['secret'] = uuid.uuid4().hex
    config['plugin'].update(
        enable=True, enable_marketplace=False, runtime_ws_url=f'ws://127.0.0.1:{runner_runtime_ports[0]}/control/ws'
    )
    config['box'].update(
        enabled=True,
        backend='docker' if backend == 'e2b' else backend,
        instance_id='full-network-' + uuid.uuid4().hex,
        file_transfer_mode='network',
        limits={'max_sessions': 1, 'max_rpc_file_bytes': 3 * 1024 * 1024},
    )
    host_root = directory / 'box-workspaces'
    host_root.mkdir()
    config['box']['local'].update(host_root=str(host_root), allowed_mount_roots=[str(host_root)], image='')
    if backend == 'nsjail':
        parent = os.environ.get('LANGBOT_NSJAIL_CGROUP_V1_PARENT')
        assert parent, 'nsjail requires the existing delegated cgroup parent'
        config['box']['nsjail'] = {'cgroup_v1_parent': parent}
    elif backend == 'e2b':
        from langbot_plugin.box.models import E2BConnectionConfig

        connection = E2BConnectionConfig(
            api_key=os.environ['E2B_API_KEY'],
            api_url=os.environ['E2B_API_URL'],
            sandbox_url=os.environ['E2B_SANDBOX_URL'],
            template=os.environ.get('E2B_TEMPLATE') or 'base',
        )
        config['box']['e2b'] = connection.model_dump()
        for name in ('E2B_API_KEY', 'E2B_API_URL', 'E2B_SANDBOX_URL', 'E2B_DOMAIN', 'E2B_TEMPLATE'):
            network_process_env.delenv(name, raising=False)
    adapters = find_project_root() / 'src/langbot/pkg/platform/sources'
    config['system']['disabled_adapters'] = [
        yaml.safe_load(item.read_text())['metadata']['name']
        for item in sorted(adapters.glob('*.yaml'))
        if item.stem not in {'http_bot', 'websocket'}
    ]
    path.write_text(yaml.safe_dump(config), encoding='utf-8')
    plugin_source = directory / 'agent-runner-qa-package'
    _write_file_runner(plugin_source)
    shutil.make_archive(str(directory / 'agent-runner-qa'), 'zip', root_dir=plugin_source)
    return path


def _provider_presence(info, expected, config):
    if info['backend_name'] == 'nsjail':
        assert Path(info['backend_session_id']).exists() == expected, info['session_id']
    elif info['backend_name'] == 'e2b':
        from e2b import AsyncSandbox
        from e2b.sandbox.sandbox_api import SandboxQuery, SandboxState

        async def check():
            pager = AsyncSandbox.list(
                query=SandboxQuery(state=[SandboxState.RUNNING, SandboxState.PAUSED]),
                limit=100,
                request_timeout=5,
                **{key: value for key, value in config.items() if key != 'template'},
            )
            found = False
            for _ in range(3):
                items = await pager.next_items()
                found |= any(item.sandbox_id == info['backend_session_id'] for item in items)
                if not pager.has_next:
                    break
            assert not pager.has_next, 'Exact provider presence exceeded its bounded listing budget'
            assert found == expected, f'Exact sandbox presence differs: {info["backend_session_id"]}'

        asyncio.run(check())


@pytest.fixture(scope='session')
def runner_langbot_process(runner_e2e_config_path, runner_e2e_port, runner_e2e_tmpdir, runner_runtime_process):
    class GracefulCore(LangBotProcess):
        token = None

        def stop(self):
            if self.process is None:
                return
            sessions = []
            try:
                if self.token and self.is_running():
                    with httpx.Client(base_url=f'http://127.0.0.1:{self.port}', trust_env=False, timeout=15) as client:
                        sessions = _data(
                            client.get('/api/v1/box/sessions', headers={'Authorization': f'Bearer {self.token}'})
                        )
                    assert len(sessions) <= 1, sessions
                    for info in sessions:
                        _provider_presence(info, True, self.e2b_config)
            finally:
                if self.process.poll() is None:
                    # Signal Core alone so it can SHUTDOWN its live stdio Box child.
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        super().stop()
                        raise AssertionError('Core did not complete graceful shutdown in 30 seconds')
                for stream in (self._stdout_file, self._stderr_file):
                    if stream:
                        stream.close()
                self._stdout_file = self._stderr_file = None
                self._stdout_data = self._stdout_path.read_bytes()
                self._stderr_data = self._stderr_path.read_bytes()
                self.process = None
            for info in sessions:
                _provider_presence(info, False, self.e2b_config)
            print(json.dumps({'event': 'core_stopped', 'sessions_removed': len(sessions)}), flush=True)

    proc = GracefulCore(
        find_project_root(),
        runner_e2e_tmpdir,
        port=runner_e2e_port,
        timeout=360,
        collect_coverage=False,
        cli_args=['--standalone-runtime'],
    )
    proc.e2b_config = yaml.safe_load(runner_e2e_config_path.read_text())['box']['e2b']
    assert proc.start(), proc.get_logs()
    try:
        yield proc
    finally:
        proc.stop()


@pytest.fixture
def file_source():
    content = os.urandom(2 * 1024 * 1024)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path != '/input.bin':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            self.send_error(500, 'sync delivery must not use callback')

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', content, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def _data(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['code'] == 0, payload
    return payload['data']


def _turn(client, bot_id, request, *, url=None, session='file-owner'):
    components = [{'type': 'Plain', 'text': json.dumps(request)}]
    if url:
        components.append({'type': 'File', 'name': 'input.bin', 'url': url + '/input.bin'})
    body = json.dumps({'session_id': session, 'session_type': 'person', 'message': components}).encode()
    timestamp, signature = signing.sign(_SECRET, body)
    result = _data(
        client.post(
            f'/bots/{bot_id}/sync',
            content=body,
            headers={
                'Content-Type': 'application/json',
                signing.HEADER_TIMESTAMP: timestamp,
                signing.HEADER_SIGNATURE: signature,
            },
            timeout=180,
        )
    )
    reports = [
        item['text'].removeprefix('NETWORK_E2E ')
        for item in result['message']
        if item['type'] == 'Plain' and item.get('text', '').startswith('NETWORK_E2E ')
    ]
    assert len(reports) == 1, result
    report = json.loads(reports[0])
    print(json.dumps({'event': 'network_plugin_turn', **report}), flush=True)
    return report, [item for item in result['message'] if item['type'] == 'File']


def _read_installation(db_path):
    with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as db:
        row = db.execute(
            'SELECT installation_uuid, artifact_digest, runtime_revision, enabled, '
            'permission_grants, permission_snapshot, workspace_uuid FROM plugin_settings '
            'WHERE plugin_author=? AND plugin_name=?',
            ('e2e', 'agent-runner-qa'),
        ).fetchone()
    assert row and row[3] and len(row[1]) == 64, row
    assert set(json.loads(row[4])['capabilities']) == {'sandbox', 'bot.message.send'}, row
    assert set(json.loads(row[5])['capabilities']) == {'sandbox', 'bot.message.send'}, row
    return row


def _completed_snapshot(db_path, run_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as db:
            row = db.execute(
                'SELECT status, runner_id, authorization_json FROM agent_run WHERE run_id=?', (run_id,)
            ).fetchone()
        if row and row[0] == 'completed':
            assert row[1] == QA_RUNNER_ID, row
            return json.loads(row[2])
        time.sleep(0.1)
    raise AssertionError(f'Run did not persist as completed: {run_id}: {row}')


def test_registered_runner_persistent_grants_and_tcp_file_delivery(
    runner_client,
    runner_langbot_process,
    runner_e2e_tmpdir,
    file_source,
):
    client = runner_client
    token = _init_and_auth(client)
    runner_langbot_process.token = token
    headers = {'Authorization': f'Bearer {token}'}
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    db_path = runner_e2e_tmpdir / 'data/langbot.db'
    before = _read_installation(db_path)
    source_url, content, source_requests = file_source
    backend = os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host')
    image = runner_langbot_process.e2b_config['template'] if backend == 'e2b' else ''
    if backend != 'host':
        selection = {'backend': backend, 'limits': {'timeout_sec': 10, 'idle_ttl_sec': 60, 'max_sessions': 1}}
        if backend == 'e2b':
            selection['e2b'] = runner_langbot_process.e2b_config
        else:
            selection['limits'].update(cpus=0.25, memory_mb=128, pids_limit=32)
        saved = _data(client.put('/api/v1/workspaces/current/sandbox', headers=headers, json=selection))
        assert saved['effective_backend'] == backend
    agent_id = _data(
        client.post(
            '/api/v1/agents',
            headers=headers,
            json={
                'kind': 'agent',
                'name': 'Full Runtime File Runner',
                'supported_event_patterns': ['message.*'],
                'config': {
                    'runner': {'id': QA_RUNNER_ID},
                    'runner_config': {QA_RUNNER_ID: {'reuse_key': uuid.uuid4().hex, 'image': image}},
                    'allowed_tools': ['exec'],
                    'allowed_platform_tools': ['event_reply'],
                },
            },
        )
    )['uuid']
    bot_id = _data(
        client.post(
            '/api/v1/platform/bots',
            headers=headers,
            json={
                'name': 'Full Runtime HTTP Files',
                'adapter': 'http_bot',
                'enable': True,
                'adapter_config': {
                    'inbound_secret': _SECRET,
                    'callback_url': source_url + '/unexpected-callback',
                    'signature_required': True,
                    'callback_timeout': 40,
                    'callback_max_retries': 0,
                },
                'event_bindings': [
                    {
                        'event_pattern': 'message.received',
                        'target_type': 'agent',
                        'target_uuid': agent_id,
                        'filters': [],
                        'priority': 0,
                        'enabled': True,
                    }
                ],
            },
        )
    )['uuid']

    def roundtrip():
        report, files = _turn(client, bot_id, {'operation': 'roundtrip'}, url=source_url)
        assert 'error' not in report, report
        assert report['size'] == len(content)
        assert report['sha256'] == hashlib.sha256(content).hexdigest()
        assert len(files) == 1, files
        assert base64.b64decode(files[0]['base64'].split(';base64,')[-1], validate=True) == content
        snapshot = _completed_snapshot(db_path, report['run_id'])
        assert snapshot['plugin_identity'] == 'e2e/agent-runner-qa'
        assert snapshot['runner_id'] == QA_RUNNER_ID
        assert snapshot['processor_id'] == agent_id and snapshot['bot_id'] == bot_id
        assert snapshot['workspace_id'] == before[6]
        assert snapshot['available_apis']['run_get']
        names = {item['tool_name'] for item in snapshot['resources']['tools']}
        assert {'exec', 'event_reply'} <= names, snapshot['resources']
        return report

    first = roundtrip()
    denied, files = _turn(client, bot_id, {'operation': 'foreign-file', 'file_id': first['file_id']})
    assert denied.get('denied') and 'error' not in denied and not files, denied
    assert denied['run_id'] != first['run_id']
    foreign, files = _turn(
        client, bot_id, {'operation': 'foreign-ledger', 'run_id': first['run_id']}, session='foreign-conversation'
    )
    assert foreign.get('denied') and not files and 'error' not in foreign, foreign

    runner_langbot_process.stop()
    for name in ('langbot.stdout.log', 'langbot.stderr.log'):
        shutil.copyfile(runner_e2e_tmpdir / name, runner_e2e_tmpdir / ('before-restart-' + name))
    assert runner_langbot_process.start(), runner_langbot_process.get_logs()
    assert QA_RUNNER_ID in _wait_for_qa_runner(client, token)
    assert _read_installation(db_path) == before
    persisted, files = _turn(client, bot_id, {'operation': 'persisted', 'run_id': first['run_id']})
    assert persisted.get('persisted_run') == first['run_id'], persisted
    assert persisted.get('persisted_status') == 'completed' and not files, persisted
    roundtrip()
    assert source_requests == ['/input.bin', '/input.bin'], source_requests

    _data(
        client.put(
            _PERMISSIONS,
            headers=headers,
            json={
                'workspace_operations': [],
                'capabilities': ['bot.message.send'],
                'confirm': False,
            },
        )
    )
    revoked, files = _turn(client, bot_id, {'operation': 'revoked'})
    assert revoked.get('error') and 'unexpected_sandbox_access' not in revoked and not files, revoked
    assert any(word in revoked['error'].lower() for word in ('permission', 'capability', 'sandbox', 'denied')), revoked
    with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as db:
        grants = db.execute(
            'SELECT permission_grants FROM plugin_settings WHERE installation_uuid=?', (before[0],)
        ).fetchone()
    assert json.loads(grants[0])['capabilities'] == ['bot.message.send']
