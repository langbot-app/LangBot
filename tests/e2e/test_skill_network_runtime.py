"""Two real Core replicas use independent Runtime filesystems for Skill tools.

Run on Linux with LANGBOT_SKILL_NETWORK_E2E=1 and the disposable PostgreSQL
configuration documented in CROSS_COMPONENT_TESTING.md. No shared data path is
configured between Core, Plugin Runtime and Box Runtime.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
import uuid
import zipfile

import pytest
import yaml
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine

from langbot_plugin.box.models import E2BConnectionConfig
from langbot.pkg.entity.persistence.workspace import Workspace
from tests.e2e.test_network_file_plugin_runtime import _SECRET, _provider_presence, _turn, _write_file_runner
from tests.e2e.test_runner_plugin_runtime import QA_RUNNER_ID, _ensure_qa_plugin, _free_port, _wait_for_qa_runner
from tests.e2e import test_skill_persistence_replicas as persistence_tests
from tests.integration.skill.test_persistent_skill_replicas import _NAME, _zip_package

core_pair = persistence_tests.core_pair
_data, _start, _stop = persistence_tests._data, persistence_tests._start, persistence_tests._stop

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skill_network,
    pytest.mark.contract('two_core_skill_network'),
    pytest.mark.skipif(os.environ.get('LANGBOT_SKILL_NETWORK_E2E') != '1', reason='explicit Skill Runtime acceptance'),
]

_TOOLS = ['activate', 'read_skill_resource', 'exec', 'register_skill']
_SCRIPT_V2 = 'print("network publication two")\n'
_GUIDE_V2 = 'Network publication two resource\n'


def _write_skill_runner(root):
    _write_file_runner(root)
    (root / 'components/runner/default.py').write_text(
        textwrap.dedent("""\
        import asyncio
        import json
        import shlex
        import urllib.request
        from langbot_plugin.api.definition.components.runner.runner import Runner
        from langbot_plugin.api.entities.builtin.runner.result import RunnerResult

        class DefaultRunner(Runner):
            async def run(self, ctx):
                request, _ = json.JSONDecoder().raw_decode(ctx.input.to_text().lstrip())
                report = {'run_id': ctx.run_id, 'operation': request['operation']}
                async def gate(name):
                    if request.get('gate'):
                        def wait():
                            with urllib.request.urlopen(request['gate'] + '/' + name, timeout=60) as response:
                                assert response.status == 200
                        await asyncio.to_thread(wait)
                try:
                    status = await ctx.api.get_box_status()
                    options = {'image': ctx.config['image']} if ctx.config.get('image') else {}
                    box = await ctx.api.acquire_box(status.required_reuse_key or ctx.config['reuse_key'], options)
                    await ctx.bind_box(box.id)
                    report['box_id'] = box.id
                    if request['operation'] == 'probe':
                        report['activation'] = await ctx.call_tool('activate', {'skill_name': request['name']})
                        await gate('pinned')
                        report['again'] = await ctx.call_tool('activate', {'skill_name': request['name']})
                        report['resource'] = await ctx.call_tool('read_skill_resource', {
                            'skill_name': request['name'], 'path': 'references/guide.md'})
                        await gate('before-exec')
                        report['execution'] = await ctx.call_tool('exec', {
                            'command': 'python3 ' + shlex.quote(report['activation']['mount_path'] + '/scripts/probe.py'),
                            'timeout_sec': 10})
                    elif request['operation'] == 'publish':
                        path = '/workspace/skill-drafts/' + ctx.run_id
                        files = {
                            'SKILL.md': '---\\nname: ' + request['name'] + '\\ndescription: Runtime draft\\n---\\nRuntime draft instructions\\n',
                            'scripts/probe.py': request.get('script', 'print("runtime draft bytes")\\n'),
                            'references/guide.md': request.get('guide', 'Runtime draft resource\\n'),
                        }
                        source = ('import pathlib; root=pathlib.Path(' + repr(path) + '); '
                                  'files=' + repr(files) + '; '
                                  '[(root.joinpath(p).parent.mkdir(parents=True,exist_ok=True), '
                                  'root.joinpath(p).write_text(v)) for p,v in files.items()]')
                        result = await ctx.call_tool('exec', {'command': 'python3 -c ' + shlex.quote(source)})
                        assert result['ok'], result
                        parameters = {'path': path, 'name': request['name']}
                        if request.get('base_revision'):
                            parameters['base_revision'] = request['base_revision']
                        report['published'] = await ctx.call_tool('register_skill', parameters)
                        cleanup_source = "import pathlib; print(list(pathlib.Path('/workspace/.langbot-snapshots').rglob('.langbot-export-*')))"
                        cleanup = await ctx.call_tool('exec', {'command': 'python3 -c ' + shlex.quote(cleanup_source)})
                        assert cleanup['ok'] and cleanup['stdout'].strip() == '[]', cleanup
                    elif request['operation'] == 'denied':
                        report['unexpected'] = await ctx.call_tool(request['tool'], request['parameters'])
                    elif request['operation'] == 'cancel':
                        await ctx.log('SKILL_NETWORK_CANCEL_READY ' + ctx.run_id)
                        await ctx.call_tool('exec', {'command': 'sleep 60', 'timeout_sec': 90})
                except Exception as error:
                    report['error'] = str(error)
                await ctx.reply('NETWORK_E2E ' + json.dumps(report))
                yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
        """),
        encoding='utf-8',
    )


@pytest.fixture
def core_pair_configure(tmp_path, monkeypatch):
    processes = []
    backend = os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host')
    assert backend in {'host', 'docker', 'nsjail', 'e2b'}
    connection = None
    if backend == 'e2b':
        connection = E2BConnectionConfig(
            api_key=os.environ['E2B_API_KEY'],
            api_url=os.environ['E2B_API_URL'],
            sandbox_url=os.environ['E2B_SANDBOX_URL'],
            template=os.environ.get('E2B_TEMPLATE') or 'base',
        )
        for name in ('E2B_API_KEY', 'E2B_API_URL', 'E2B_SANDBOX_URL', 'E2B_DOMAIN', 'E2B_TEMPLATE'):
            monkeypatch.delenv(name, raising=False)
    token = secrets.token_urlsafe(48)
    monkeypatch.setenv('LANGBOT_BOX_CONTROL_TOKEN', token)
    for name in ('LANGBOT_BOX_CONFIG', 'LANGBOT_BOX_INSTANCE_ID', 'LANGBOT_BOX_TRUSTED_INSTANCE_UUID'):
        monkeypatch.delenv(name, raising=False)

    def launch(root, name, arguments, extra_env):
        root.mkdir()
        environment = {**os.environ, **extra_env, 'PYTHONDONTWRITEBYTECODE': '1'}
        streams = [open(root / (name + suffix), 'wb') for suffix in ('.stdout.log', '.stderr.log')]
        process = subprocess.Popen(
            [sys.executable, '-m', 'langbot_plugin.cli.__init__', *arguments],
            cwd=root,
            env=environment,
            stdout=streams[0],
            stderr=streams[1],
            start_new_session=True,
        )
        processes.append((process, streams))

    def configure(root, config):
        runtime_root = tmp_path / (root.name + '-runtimes')
        runtime_root.mkdir()
        plugin_port, debug_port, box_port = (_free_port() for _ in range(3))
        assert len({plugin_port, debug_port, box_port}) == 3
        instance_id = root.name + '-' + uuid.uuid4().hex
        box_root = runtime_root / 'box'
        runtime_config = {
            'backend': 'docker' if backend == 'e2b' else backend,
            'local': {'host_root': str(box_root / 'workspaces'), 'allowed_mount_roots': [str(box_root)]},
            'limits': {'max_sessions': 1},
        }
        if backend == 'nsjail':
            parent = os.environ.get('LANGBOT_NSJAIL_CGROUP_V1_PARENT')
            assert parent, 'nsjail requires the existing delegated cgroup parent'
            runtime_config['nsjail'] = {'cgroup_v1_parent': parent}
        elif backend == 'e2b':
            config['box']['e2b'] = connection.model_dump()
        launch(
            runtime_root / 'plugin',
            'plugin-runtime',
            ['rt', '--ws-control-port', str(plugin_port), '--ws-debug-port', str(debug_port)],
            {'LANGBOT_PLUGIN_FILE_STORAGE_DIR': str(runtime_root / 'plugin-transfers')},
        )
        launch(
            box_root,
            'box-runtime',
            [
                'box',
                '--host',
                '127.0.0.1',
                '--ws-control-port',
                str(box_port),
                '--instance-id',
                instance_id,
                '--data-dir',
                str(box_root / 'identity'),
            ],
            {
                'LANGBOT_BOX_CONFIG': json.dumps(runtime_config),
                'LANGBOT_BOX_TRUSTED_INSTANCE_UUID': config['system']['instance_id'],
                'LANGBOT_PLUGIN_FILE_STORAGE_DIR': str(runtime_root / 'box-transfers'),
            },
        )
        deadline = time.monotonic() + 30
        for port in (plugin_port, box_port):
            while True:
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=1):
                        break
                except OSError:
                    assert all(process.poll() is None for process, _ in processes), 'Runtime exited during startup'
                    assert time.monotonic() < deadline, 'Runtime did not listen in 30 seconds'
                    time.sleep(0.1)
        config['plugin'].update(enable=True, runtime_ws_url=f'ws://127.0.0.1:{plugin_port}/control/ws')
        config['box'].update(
            enabled=True,
            backend='docker' if backend == 'e2b' else backend,
            instance_id=instance_id,
            file_transfer_mode='network',
            runtime={'endpoint': f'http://127.0.0.1:{box_port}'},
        )
        config['box']['local'].update(host_root='', default_workspace='', allowed_mount_roots=[])
        config['system']['disabled_adapters'] = [
            name for name in config['system']['disabled_adapters'] if name != 'http_bot'
        ]
        return ['--standalone-runtime', '--standalone-box']

    configure.sessions = []
    try:
        yield configure
    finally:
        timed_out = []
        for process, streams in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                    timed_out.append(process.pid)
            for stream in streams:
                stream.close()
        assert not timed_out, f'Runtime did not finish graceful shutdown in 30 seconds: {timed_out}'
        for info, connection in configure.sessions:
            _backend_presence(info, False, connection)


@pytest.fixture
def publication_gate():
    arrived = {name: threading.Event() for name in ('pinned', 'before-exec')}
    release = {name: threading.Event() for name in arrived}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            name = self.path.removeprefix('/')
            if name not in arrived:
                self.send_error(404)
                return
            arrived[name].set()
            if not release[name].wait(60):
                self.send_error(504)
                return
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', arrived, release
    finally:
        for event in release.values():
            event.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def _create_agent_bot(replica, headers, tools):
    backend = os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host')
    image = 'python:3.12-alpine' if backend == 'docker' else ''
    if backend == 'e2b':
        image = yaml.safe_load((replica.root / 'data/config.yaml').read_text())['box']['e2b']['template']
    agent = _data(
        replica.client.post(
            '/api/v1/agents',
            headers=headers,
            json={
                'kind': 'agent',
                'name': 'Network Skill tools',
                'supported_event_patterns': ['message.*'],
                'config': {
                    'runner': {'id': QA_RUNNER_ID},
                    'runner_config': {
                        QA_RUNNER_ID: {'reuse_key': 'skill-network-' + replica.root.name, 'image': image}
                    },
                    'allowed_tools': tools,
                    'allowed_platform_tools': ['event_reply'],
                },
            },
        )
    )['uuid']
    bot = _data(
        replica.client.post(
            '/api/v1/platform/bots',
            headers=headers,
            json={
                'name': 'Network Skills HTTP',
                'adapter': 'http_bot',
                'enable': True,
                'adapter_config': {'inbound_secret': _SECRET, 'signature_required': True, 'callback_url': ''},
                'event_bindings': [
                    {
                        'event_pattern': 'message.received',
                        'target_type': 'agent',
                        'target_uuid': agent,
                        'filters': [],
                        'priority': 0,
                        'enabled': True,
                    }
                ],
            },
        )
    )['uuid']
    return agent, bot


def _probe(replica, bot, name=_NAME, **request):
    report, files = _turn(replica.client, bot, {'operation': 'probe', 'name': name, **request})
    assert 'error' not in report and not files, report
    assert report['execution']['ok'], report
    return report


def _assert_probe(report, revision, output, guide='# Replica guide\nOriginal reference bytes.\n'):
    assert report['activation']['revision'] == report['again']['revision'] == revision, report
    assert report['execution']['stdout'].strip() == output, report
    assert report['resource']['content'] == guide, report


def _assert_no_core_cache(pair):
    for replica in (pair.a, pair.b):
        assert not (replica.root / 'skills/.database-cache').exists(), replica.root


def _run_record(replica, headers, agent, run_id):
    items = _data(replica.client.get(f'/api/v1/agents/{agent}/runs', headers=headers))['items']
    return next((item for item in items if item['run_id'] == run_id), None)


def _foreign_workspace():
    workspace = str(uuid.uuid4())

    async def seed():
        engine = create_async_engine(os.environ['LANGBOT_PERSISTENCE_CORE_POSTGRES_URL'])
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(Workspace).values(
                        uuid=workspace,
                        instance_uuid='foreign-' + uuid.uuid4().hex,
                        name='Foreign acceptance Workspace',
                        slug='foreign',
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())
    return workspace


def _backend_presence(info, expected, connection):
    if info['backend_name'] == 'docker':
        result = subprocess.run(
            [
                'docker',
                'container',
                'ls',
                '--all',
                '--filter',
                f'name=^/{info["backend_session_id"]}$',
                '--format',
                '{{.ID}}',
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert bool(result.stdout.strip()) == expected, info['session_id']
    else:
        _provider_presence(info, expected, connection)


def test_two_cores_use_independent_runtimes_for_pinned_skills_and_drafts(
    core_pair,
    core_pair_configure,
    publication_gate,
):
    a, b = core_pair.a, core_pair.b
    headers = {'Authorization': f'Bearer {core_pair.token}'}
    backend = os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host')
    if backend != 'host':
        selection = {'backend': backend, 'limits': {'timeout_sec': 90, 'idle_ttl_sec': 300, 'max_sessions': 1}}
        if backend == 'e2b':
            selection['e2b'] = yaml.safe_load((a.root / 'data/config.yaml').read_text())['box']['e2b']
        else:
            selection['limits'].update(cpus=0.25, memory_mb=128, pids_limit=32)
        saved = _data(a.client.put('/api/v1/workspaces/current/sandbox', headers=headers, json=selection))
        assert saved['effective_backend'] == backend
    source = a.root / 'qa-runner-package'
    _write_skill_runner(source)
    package = Path(shutil.make_archive(str(a.root / 'qa-runner'), 'zip', root_dir=source))
    _ensure_qa_plugin(a.client, core_pair.token, package)
    assert QA_RUNNER_ID in _wait_for_qa_runner(b.client, core_pair.token)
    permissions = '/api/v1/plugins/e2e/agent-runner-qa/permissions'
    grant = _data(a.client.get(permissions, headers=headers))
    assert grant['enabled'] and not grant['pending_confirmation']
    assert set(grant['grants']['capabilities']) == {'sandbox', 'bot.message.send'}
    agent_a, bot_a = _create_agent_bot(a, headers, _TOOLS)
    _, bot_b = _create_agent_bot(b, headers, _TOOLS)
    original = _data(
        a.client.post(
            '/api/v1/skills/install/upload',
            headers=headers,
            files={'file': ('probe.zip', _zip_package(), 'application/zip')},
        )
    )['skills'][0]['revision']
    old_url = f'/api/v1/skills/{_NAME}/package?revision={original}'
    original_package = b.client.get(old_url, headers=headers).content
    gate, arrived, release = publication_gate
    with ThreadPoolExecutor(max_workers=1) as pool:
        old_run = pool.submit(_probe, a, bot_a, gate=gate)
        try:
            assert arrived['pinned'].wait(60), 'Runner did not activate the first publication'
            _assert_no_core_cache(core_pair)
            updated, _ = _turn(
                b.client,
                bot_b,
                {
                    'operation': 'publish',
                    'name': _NAME,
                    'base_revision': original,
                    'script': _SCRIPT_V2,
                    'guide': _GUIDE_V2,
                },
            )
            assert 'error' not in updated and updated['published']['registered'], updated
            current = updated['published']['revision']
            assert current != original
            release['pinned'].set()
            assert arrived['before-exec'].wait(60), 'Runner did not finish its pinned resource read'
            _assert_no_core_cache(core_pair)
        finally:
            for event in release.values():
                event.set()
        first = old_run.result(timeout=60)
    _assert_probe(first, original, 'immutable replica bytes')
    _assert_no_core_cache(core_pair)
    old_record = _run_record(a, headers, agent_a, first['run_id'])
    assert old_record['metadata']['activated_skills'][_NAME] == original, old_record
    _assert_probe(_probe(b, bot_b), current, 'network publication two', _GUIDE_V2)
    _assert_no_core_cache(core_pair)
    for replica in (a, b):
        sessions = _data(replica.client.get('/api/v1/box/sessions', headers=headers))
        assert len(sessions) == 1 and sessions[0]['backend_name'] == backend, sessions
        connection = (
            yaml.safe_load((replica.root / 'data/config.yaml').read_text())['box']['e2b'] if backend == 'e2b' else {}
        )
        _backend_presence(sessions[0], True, connection)
        core_pair_configure.sessions.append((sessions[0], connection))
    assert a.client.get(old_url, headers=headers).content == original_package

    draft_name = 'runtime-created-probe'
    draft, files = _turn(b.client, bot_b, {'operation': 'publish', 'name': draft_name})
    assert 'error' not in draft and not files and draft['published']['registered'], draft
    _assert_no_core_cache(core_pair)
    draft_revision = draft['published']['revision']
    draft_url = f'/api/v1/skills/{draft_name}/package?revision={draft_revision}'
    published = a.client.get(draft_url, headers=headers)
    assert published.status_code == 200
    with zipfile.ZipFile(io.BytesIO(published.content)) as archive:
        assert archive.read('scripts/probe.py') == b'print("runtime draft bytes")\n'
        assert archive.read('references/guide.md') == b'Runtime draft resource\n'
    _stop(a.process)
    _start(a)
    assert QA_RUNNER_ID in _wait_for_qa_runner(a.client, core_pair.token)
    assert _data(a.client.get(permissions, headers=headers)) == grant
    assert a.client.get(draft_url, headers=headers).content == published.content
    _assert_probe(_probe(a, bot_a), current, 'network publication two', _GUIDE_V2)
    _assert_no_core_cache(core_pair)

    cancelled_run = None
    with a.client.stream(
        'POST',
        f'/api/v1/agents/{agent_a}/debug/stream',
        headers=headers,
        json={'text': json.dumps({'operation': 'cancel'})},
        timeout=30,
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line:
                continue
            frame = json.loads(line)
            assert frame['kind'] == 'result', frame
            result = frame['data']
            if result['type'] == 'processor.log' and 'SKILL_NETWORK_CANCEL_READY' in result['data']['text']:
                cancelled_run = result['run_id']
                break
    assert cancelled_run
    deadline = time.monotonic() + 15
    while True:
        record = _run_record(a, headers, agent_a, cancelled_run)
        if record and record['status'] == 'cancelled':
            break
        assert time.monotonic() < deadline, record
        time.sleep(0.1)
    _assert_probe(_probe(a, bot_a), current, 'network publication two', _GUIDE_V2)
    assert a.client.get(draft_url, headers=headers).content == published.content

    _, restricted_bot = _create_agent_bot(a, headers, ['activate', 'read_skill_resource'])
    denied, _ = _turn(
        a.client,
        restricted_bot,
        {'operation': 'denied', 'tool': 'exec', 'parameters': {'command': 'echo UNAUTHORIZED_EXECUTION'}},
    )
    assert denied.get('error') and 'unexpected' not in denied, denied
    invalid_draft, _ = _turn(
        a.client,
        bot_a,
        {
            'operation': 'denied',
            'tool': 'register_skill',
            'parameters': {'path': '/workspace/../../etc', 'name': draft_name},
        },
    )
    assert invalid_draft.get('error') and 'unexpected' not in invalid_draft, invalid_draft
    assert a.client.get(draft_url, headers=headers).content == published.content
    foreign = {**headers, 'X-Workspace-Id': _foreign_workspace()}
    assert a.client.get(draft_url, headers=foreign).status_code in {403, 404}
    _data(
        a.client.put(
            permissions,
            headers=headers,
            json={'workspace_operations': [], 'capabilities': ['bot.message.send'], 'confirm': False},
        )
    )
    revoked, _ = _turn(
        b.client, bot_b, {'operation': 'denied', 'tool': 'exec', 'parameters': {'command': 'echo REVOKED_EXECUTION'}}
    )
    assert revoked.get('error') and 'unexpected' not in revoked, revoked
    assert _data(b.client.get(permissions, headers=headers))['grants']['capabilities'] == ['bot.message.send']
    _assert_no_core_cache(core_pair)
