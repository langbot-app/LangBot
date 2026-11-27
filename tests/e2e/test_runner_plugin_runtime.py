"""E2E tests for pluginized Runner execution.

This module starts the real LangBot backend with the plugin system enabled and
loads a deterministic Runner plugin through the real SDK Plugin Runtime.
"""

from __future__ import annotations

import shutil
import json
import os
import signal
import socket
import contextlib
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import httpx
import pytest

from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.e2e.utils.process_manager import LangBotProcess, find_project_root

pytestmark = pytest.mark.e2e


QA_RUNNER_ID = 'plugin:e2e/agent-runner-qa/default'


@pytest.fixture(scope='session')
def runner_e2e_port():
    """Port for the Runner plugin-runtime E2E process."""
    return _free_port()


@pytest.fixture(scope='session')
def runner_e2e_tmpdir():
    """Create temporary directory for Runner E2E testing."""
    root = find_project_root() / '.qa' / 'lang54'
    root.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix='runner-runtime-', dir=root))
    yield tmpdir
    if not os.environ.get('LANGBOT_KEEP_RUNNER_E2E'):
        shutil.rmtree(tmpdir, ignore_errors=True)


def _write_qa_runner_plugin(plugin_root: Path) -> None:
    """Write a deterministic Runner plugin used by this E2E."""
    runner_dir = plugin_root / 'components' / 'runner'
    runner_dir.mkdir(parents=True, exist_ok=True)
    (plugin_root / 'assets').mkdir(parents=True, exist_ok=True)
    (plugin_root / 'assets' / 'icon.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>',
        encoding='utf-8',
    )
    (plugin_root / 'manifest.yaml').write_text(
        textwrap.dedent(
            """
            apiVersion: langbot/v1
            kind: Plugin
            metadata:
              author: e2e
              name: agent-runner-qa
              version: 0.1.0
              label:
                en_US: Runner QA
                zh_Hans: Runner QA
              description:
                en_US: Deterministic Runner E2E probe.
                zh_Hans: 确定性的 Runner E2E 探针。
              icon: assets/icon.svg
            spec:
              version: 0.1.0
              config: []
              components:
                Runner:
                  fromDirs:
                    - path: components/runner/
                Tool:
                  fromDirs:
                    - path: components/tools/
                Command:
                  fromDirs:
                    - path: components/commands/
                EventListener:
                  fromDirs:
                    - path: components/event_listener/
              pages: []
            execution:
              python:
                path: main.py
                attr: RunnerQAPlugin
            """
        ).strip()
        + '\n',
        encoding='utf-8',
    )
    (plugin_root / 'main.py').write_text(
        textwrap.dedent(
            """
            from __future__ import annotations

            from langbot_plugin.api.definition.plugin import BasePlugin


            class RunnerQAPlugin(BasePlugin):
                async def initialize(self) -> None:
                    pass
            """
        ).strip()
        + '\n',
        encoding='utf-8',
    )
    (runner_dir / 'default.yaml').write_text(
        textwrap.dedent(
            """
            apiVersion: langbot/v1
            kind: Runner
            metadata:
              name: default
              label:
                en_US: QA Echo Runner
                zh_Hans: QA Echo Runner
              description:
                en_US: Echoes input and exercises run-scoped state APIs.
                zh_Hans: 回显输入并验证运行级状态 API。
            spec:
              usages: [agent]
              config:
                - name: prefix
                  type: string
                  label:
                    en_US: Echo prefix
                    zh_Hans: 回显前缀
                  default: 'e2e echo'
                  required: false
              capabilities:
                streaming: false
                tool_calling: true
              permissions:
                tools: [detail, call]
            execution:
              python:
                path: default.py
                attr: DefaultRunner
            """
        ).strip()
        + '\n',
        encoding='utf-8',
    )
    (runner_dir / 'default.py').write_text(
        textwrap.dedent(
            """
            from __future__ import annotations

            from typing import AsyncGenerator
            import json
            import logging
            from pathlib import Path

            from langbot_plugin.api.definition.components.runner.runner import Runner
            from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
            from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
            from langbot_plugin.api.entities.builtin.provider.message import Message


            class DefaultRunner(Runner):
                async def run(self, ctx: RunnerContext) -> AsyncGenerator[RunnerResult, None]:
                    text = ctx.input.to_text()
                    if text == 'stream-policy-probe':
                        await ctx.call_tool('platform_send_message', {'target_type': 'group', 'target_id': 'qa-notifications', 'text': 'proactive text'})
                        async with ctx.reply_stream() as stream:
                            await stream.update('first')
                            await stream.update('first and last')
                        yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
                        return
                    if text == 'hello from orchestrator e2e':
                        logging.getLogger(__name__).warning('Runner trace probe')
                    content = f'{ctx.config.get("prefix", "e2e echo")}: {text}'
                    self.plugin.runner_inputs = getattr(self.plugin, 'runner_inputs', []) + [text]
                    if text == 'lifecycle-counts':
                        content = json.dumps({'received': self.plugin.received, 'ran': self.plugin.runner_inputs})
                    if text.startswith('boundary probe'):
                        tools = await ctx.get_available_tools()
                        names = [item['name'] for item in tools]
                        tool_name = next((name for name in names if 'qa_boundary_tool' in name), 'qa_boundary_tool')
                        try:
                            result = await ctx.call_tool(tool_name, {})
                            denied = 'QA_TOOL_EXECUTED' not in json.dumps(result)
                        except Exception as exc:
                            result = str(exc)
                            denied = True
                        content = json.dumps({
                            'tool_result': str(result),
                            'tool_names': names,
                            'tool_denied': denied,
                            'listener_hits': getattr(self.plugin, 'boundary_listener_hits', 0),
                        })
                    yield RunnerResult.message_completed(
                        ctx.run_id,
                        Message(role='assistant', content=content),
                    )
                    yield RunnerResult.state_updated(
                        ctx.run_id,
                        'e2e.echo_count',
                        {'count': 1},
                        scope='conversation',
                    )
                    yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
            """
        ).strip()
        + '\n',
        encoding='utf-8',
    )

    import yaml

    components = {
        'tools': (
            'Tool',
            'qa_boundary_tool',
            'BoundaryTool',
            {'parameters': {}, 'llm_prompt': 'QA boundary tool'},
            """
            from langbot_plugin.api.definition.components.tool.tool import Tool

            class BoundaryTool(Tool):
                async def call(self, params, session, query_id):
                    return {'result': 'QA_TOOL_EXECUTED'}
        """,
        ),
        'commands': (
            'Command',
            'qa_boundary_command',
            'BoundaryCommand',
            {},
            """
            from langbot_plugin.api.definition.components.command.command import Command
            from langbot_plugin.api.entities.builtin.command.context import CommandReturn
            from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

            class BoundaryCommand(Command):
                async def initialize(self):
                    await super().initialize()
                    @self.subcommand('')
                    async def handle(self, ctx):
                        yield CommandReturn(text='QA_COMMAND_EXECUTED')
                    @self.subcommand('query-probe')
                    async def probe(self, ctx):
                        await ctx.reply(MessageChain([Plain(text='command:' + await ctx.get_bot_uuid())]))
                        yield CommandReturn()
        """,
        ),
        'event_listener': (
            'EventListener',
            'boundary',
            'BoundaryListener',
            {},
            """
            from pathlib import Path
            from langbot_plugin.api.definition.components.common.event_listener import EventListener
            from langbot_plugin.api.entities import events
            from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

            class BoundaryListener(EventListener):
                async def initialize(self):
                    await super().initialize()
                    self.plugin.received = []
                    @self.handler(events.PersonMessageReceived)
                    async def person(ctx):
                        self.plugin.received.append(str(ctx.event.message_chain))
                    @self.handler(events.PersonNormalMessageReceived)
                    async def handle(ctx):
                        self.plugin.boundary_listener_hits = getattr(self.plugin, 'boundary_listener_hits', 0) + 1
                        if 'agent-probe intercept' in ctx.event.text_message:
                            ctx.event.reply_message_chain = MessageChain([Plain(text='handled before agent')])
                            ctx.prevent_default()
                        elif 'agent-probe replace-input' in ctx.event.text_message:
                            ctx.event.user_message_alter = 'updated input'
                    @self.handler(events.NormalMessageResponded)
                    async def responded(ctx):
                        if ctx.event.response_text == 'e2e echo: agent-probe replace-output':
                            ctx.event.reply_message_chain = MessageChain([Plain(text='updated output')])
                    @self.handler(events.GroupMessageReceived)
                    async def group(ctx):
                        self.plugin.received.append(str(ctx.event.message_chain))
                        if 'group-probe' in str(ctx.event.message_chain):
                            await ctx.reply(MessageChain([Plain(text='group:' + await ctx.get_bot_uuid())]))
                            ctx.prevent_default()
        """,
        ),
    }
    for directory, (kind, name, attr, spec, source) in components.items():
        target = plugin_root / 'components' / directory
        target.mkdir(parents=True, exist_ok=True)
        (target / f'{name}.yaml').write_text(
            yaml.safe_dump(
                {
                    'apiVersion': 'v1',
                    'kind': kind,
                    'metadata': {'name': name, 'label': {'en_US': name}, 'description': {'en_US': name}},
                    'spec': spec,
                    'execution': {'python': {'path': f'{name}.py', 'attr': attr}},
                }
            ),
            encoding='utf-8',
        )
        (target / f'{name}.py').write_text(textwrap.dedent(source), encoding='utf-8')

    processor_dir = runner_dir
    (processor_dir / 'welcome.yaml').write_text(
        textwrap.dedent("""
        apiVersion: langbot/v1
        kind: Runner
        metadata:
          name: welcome
          label: {en_US: Welcome processor, zh_Hans: Welcome processor}
        spec:
          usages: [event]
          events: [group.member_joined, message.received]
          config:
            - name: greeting
              type: string
              required: true
              label: {en_US: Greeting, zh_Hans: Greeting}
              default: Hello
          capabilities: {tool_calling: true}
          permissions:
            tools: [detail, call]
        execution:
          python: {path: welcome.py, attr: WelcomeProcessor}
    """)
    )
    (processor_dir / 'welcome.py').write_text(
        textwrap.dedent("""
        from langbot_plugin.api.definition.components.runner import Runner, RunnerContext
        from langbot_plugin.api.entities.builtin.platform.events import MemberJoinedEvent, MessageReceivedEvent

        class WelcomeProcessor(Runner):
            async def initialize(self):
                @self.handler(MessageReceivedEvent)
                async def message(ctx: RunnerContext):
                    await self.plugin.call_tool('event_reply', {'text': ctx.config['greeting']})

                @self.handler(MemberJoinedEvent)
                async def handle(ctx: RunnerContext):
                    await ctx.log('Handling ' + str(ctx.platform_event.member.id))
                    tools = await ctx.get_available_tools()
                    assert any(tool['name'] == 'event_reply' for tool in tools)
                    result = await self.plugin.call_tool('event_reply', {'text': ctx.config['greeting'] + ', ' + (ctx.platform_event.member.nickname or str(ctx.platform_event.member.id))})
                    await ctx.log('Reply simulated: ' + str(result.get('mock')))
    """)
    )


def _free_port() -> int:
    """Reserve a currently-free localhost TCP port for this E2E process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope='session')
def runner_runtime_ports():
    """Control/debug ports for the standalone plugin runtime."""
    control_port = _free_port()
    debug_port = _free_port()
    while debug_port == control_port:
        debug_port = _free_port()
    return control_port, debug_port


@pytest.fixture(scope='session')
def runner_e2e_config_path(runner_e2e_tmpdir, runner_e2e_port, runner_runtime_ports):
    """Create a plugin-enabled config and deterministic Runner fixture."""
    config_path = create_minimal_config(runner_e2e_tmpdir, port=runner_e2e_port)
    create_test_directories(runner_e2e_tmpdir)

    import yaml

    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)
    config['api']['global_api_key'] = 'e2e-agent-runner-key'
    runtime_control_port, _runtime_debug_port = runner_runtime_ports
    config['plugin']['enable'] = True
    config['plugin']['runtime_ws_url'] = f'ws://127.0.0.1:{runtime_control_port}/control/ws'
    config['plugin']['enable_marketplace'] = False
    config['box']['enabled'] = False
    config['system']['jwt']['secret'] = 'e2e-agent-runner-secret-key'
    adapters = find_project_root() / 'src' / 'langbot' / 'pkg' / 'platform' / 'sources'
    config['system']['disabled_adapters'] = [
        yaml.safe_load(path.read_text(encoding='utf-8'))['metadata']['name']
        for path in sorted(adapters.glob('*.yaml'))
        if path.stem not in {'websocket', 'http_bot'}
    ]
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    plugin_source = runner_e2e_tmpdir / 'agent-runner-qa-package'
    _write_qa_runner_plugin(plugin_source)
    shutil.make_archive(
        str(runner_e2e_tmpdir / 'agent-runner-qa'),
        'zip',
        root_dir=plugin_source,
    )
    return config_path


@pytest.fixture(scope='session')
def runner_runtime_process(runner_e2e_tmpdir, runner_runtime_ports):
    """Start the real SDK plugin runtime over WebSocket."""
    control_port, debug_port = runner_runtime_ports
    stdout_path = runner_e2e_tmpdir / 'plugin-runtime.stdout.log'
    stderr_path = runner_e2e_tmpdir / 'plugin-runtime.stderr.log'
    stdout_file = open(stdout_path, 'wb')
    stderr_file = open(stderr_path, 'wb')
    proc = subprocess.Popen(
        [
            sys.executable,
            '-m',
            'langbot_plugin.cli.__init__',
            'rt',
            '--ws-control-port',
            str(control_port),
            '--ws-debug-port',
            str(debug_port),
        ],
        cwd=runner_e2e_tmpdir,
        stdout=stdout_file,
        stderr=stderr_file,
        start_new_session=True,
    )
    yield proc
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    except ProcessLookupError:
        pass
    stdout_file.close()
    stderr_file.close()


@pytest.fixture(scope='session')
def runner_langbot_process(
    runner_e2e_config_path,
    runner_e2e_port,
    runner_e2e_tmpdir,
    runner_runtime_process,
):
    """Start real LangBot with plugin runtime enabled."""
    project_root = find_project_root()
    proc = LangBotProcess(
        project_root=project_root,
        work_dir=runner_e2e_tmpdir,
        port=runner_e2e_port,
        timeout=360,
        debug=False,
        collect_coverage=False,
        cli_args=['--standalone-runtime'],
    )

    success = proc.start()
    if not success:
        stdout, stderr = proc.get_logs()
        pytest.fail(f'LangBot failed to start with Runner plugin runtime:\nstdout: {stdout}\nstderr: {stderr}')

    yield proc

    proc.stop()


@pytest.fixture
def runner_client(runner_e2e_port, runner_langbot_process):
    """HTTP client for the Runner E2E backend."""
    with httpx.Client(
        base_url=f'http://127.0.0.1:{runner_e2e_port}',
        timeout=90.0,
        trust_env=False,
    ) as client:
        yield client


def _init_and_auth(client: httpx.Client) -> str:
    """Initialize the test admin user and return a bearer token."""
    credentials = {'user': 'admin@langbot.test', 'password': 'admin'}
    init_resp = client.post('/api/v1/user/init', json=credentials)
    assert init_resp.status_code == 200
    assert init_resp.json()['code'] in [0, 1]

    auth_resp = client.post('/api/v1/user/auth', json=credentials)
    assert auth_resp.status_code == 200
    payload = auth_resp.json()
    assert payload['code'] == 0
    return payload['data']['token']


def _install_qa_plugin(client: httpx.Client, token: str, package_path: Path, runner_id=QA_RUNNER_ID) -> None:
    """Install the QA Runner through the same asynchronous local-upload API as the UI."""
    headers = {'Authorization': f'Bearer {token}'}
    with package_path.open('rb') as package_file:
        response = client.post(
            '/api/v1/plugins/install/local',
            headers=headers,
            files={'file': ('agent-runner-qa.zip', package_file, 'application/zip')},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['code'] == 0, payload
    task_id = payload['data']['task_id']

    deadline = time.time() + 90
    while time.time() < deadline:
        task_response = client.get(f'/api/v1/system/tasks/{task_id}', headers=headers)
        assert task_response.status_code == 200, task_response.text
        task_payload = task_response.json()
        assert task_payload['code'] == 0, task_payload
        task = task_payload['data']
        if task['runtime']['done']:
            assert task['runtime']['exception'] is None, task
            metadata = task['task_context']['metadata']
            if metadata.get('pending_permission_confirmation'):
                # A fresh installation stays disabled until an account confirms it.
                _confirm_qa_plugin_permissions(client, token, runner_id)
                return
            assert metadata['progress_percent'] == 100
            return
        time.sleep(1)
    raise AssertionError(f'Plugin installation task {task_id} did not complete')


def _confirm_qa_plugin_permissions(client: httpx.Client, token: str, runner_id=QA_RUNNER_ID) -> None:
    """Grant every declared permission, as the WebUI grant dialog does."""
    author, name = runner_id.removeprefix('plugin:').split('/')[:2]
    path = f'/api/v1/plugins/{author}/{name}/permissions'
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    state = response.json()['data']
    grants = {
        category: [item['id'] for item in state['permissions'] if item['category'] == category]
        for category in ('workspace_operations', 'capabilities')
    }
    response = client.put(path, headers=headers, json={**grants, 'confirm': True})
    assert response.status_code == 200, response.text
    assert response.json()['code'] == 0, response.text


def _wait_for_qa_runner(client: httpx.Client, token: str, timeout: float = 60, runner_id=QA_RUNNER_ID) -> set[str]:
    """Return the latest Runner option set, waiting for the QA Runner when needed."""
    deadline = time.time() + timeout
    option_names: set[str] = set()
    while time.time() < deadline:
        response = client.get(
            '/api/v1/pipelines/_/metadata',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['code'] == 0, data
        metadata_groups = data['data']['configs']
        ai_metadata = next(group for group in metadata_groups if group.get('name') == 'ai')
        runner_stage = next(stage for stage in ai_metadata['stages'] if stage['name'] == 'runner')
        runner_select = next(item for item in runner_stage['config'] if item['name'] == 'id')
        # Metadata can precede Runtime reconnection after a Core restart.
        option_names = {option['name'] for option in runner_select.get('options', [])}
        if runner_id in option_names:
            break
        time.sleep(1)
    return option_names


def _ensure_qa_plugin(client: httpx.Client, token: str, package_path: Path) -> None:
    if QA_RUNNER_ID in _wait_for_qa_runner(client, token, timeout=2):
        return
    _install_qa_plugin(client, token, package_path)
    # Confirmed installations start asynchronously; callers need the Runner.
    assert QA_RUNNER_ID in _wait_for_qa_runner(client, token)


def test_plugin_runtime_discovers_runner(
    runner_client,
    runner_langbot_process,
    runner_e2e_tmpdir,
):
    """Pipeline metadata should include the real runtime-discovered QA runner."""
    token = _init_and_auth(runner_client)
    _ensure_qa_plugin(
        runner_client,
        token,
        runner_e2e_tmpdir / 'agent-runner-qa.zip',
    )
    option_names = _wait_for_qa_runner(runner_client, token)
    if QA_RUNNER_ID in option_names:
        return

    host_stdout, host_stderr = runner_langbot_process.get_logs()
    runtime_stdout = (runner_e2e_tmpdir / 'plugin-runtime.stdout.log').read_text(encoding='utf-8', errors='replace')
    runtime_stderr = (runner_e2e_tmpdir / 'plugin-runtime.stderr.log').read_text(encoding='utf-8', errors='replace')
    assert QA_RUNNER_ID in option_names, (
        f'{QA_RUNNER_ID} was not discovered\n'
        f'Host stdout (tail):\n{host_stdout[-20_000:]}\nHost stderr (tail):\n{host_stderr[-20_000:]}\n'
        f'Runtime stdout (tail):\n{runtime_stdout[-20_000:]}\n'
        f'Runtime stderr (tail):\n{runtime_stderr[-20_000:]}'
    )


def test_host_orchestrator_runs_runner_and_records_ledger(
    runner_client,
    runner_langbot_process,
    runner_e2e_tmpdir,
):
    """Create/configure/debug an Agent through HTTP and persist Runner side effects."""
    del runner_langbot_process
    token = _init_and_auth(runner_client)
    _ensure_qa_plugin(
        runner_client,
        token,
        runner_e2e_tmpdir / 'agent-runner-qa.zip',
    )
    headers = {'Authorization': f'Bearer {token}'}
    create_response = runner_client.post(
        '/api/v1/agents',
        headers=headers,
        json={
            'kind': 'agent',
            'name': 'Runner E2E Agent',
            'description': 'Exercises the installed QA Runner.',
            'emoji': 'QA',
            'supported_event_patterns': ['message.*'],
            'config': {
                'runner': {'id': QA_RUNNER_ID},
                'runner_config': {QA_RUNNER_ID: {}},
                'allowed_platform_tools': ['event_reply', 'platform_get_user_info'],
            },
        },
    )
    assert create_response.status_code == 200, create_response.text
    create_payload = create_response.json()
    assert create_payload['code'] == 0, create_payload
    agent_uuid = create_payload['data']['uuid']

    get_response = runner_client.get(f'/api/v1/agents/{agent_uuid}', headers=headers)
    assert get_response.status_code == 200, get_response.text
    stored_agent = get_response.json()['data']['agent']
    assert stored_agent['config']['allowed_platform_tools'] == [
        'event_reply',
        'platform_get_user_info',
    ]

    debug_response = runner_client.post(
        f'/api/v1/agents/{agent_uuid}/debug',
        headers=headers,
        json={
            'event_type': 'message.received',
            'text': 'hello from orchestrator e2e',
            'conversation_id': 'e2e-conversation',
        },
    )
    assert debug_response.status_code == 200, debug_response.text
    debug_payload = debug_response.json()
    assert debug_payload['code'] == 0, debug_payload
    result = debug_payload['data']
    assert result['final_text'] == 'e2e echo: hello from orchestrator e2e'
    assert result['outputs'][0]['role'] == 'assistant'

    from tools.regression.service_logs import records

    runtime_file = runner_e2e_tmpdir / 'plugin-runtime.stderr.log'
    with runtime_file.open() as stream:
        warning = next(row for row in records(stream, 'runtime') if row.msg == 'Runner trace probe')
    assert warning.module == 'PLUGIN.e2e/agent-runner-qa' and warning.level == 'WARN'
    assert warning.trace.startswith('Y-')
    detail = runner_client.get('/api/v1/plugins/e2e/agent-runner-qa/logs?level=WARNING', headers=headers)
    assert any(
        row['level'] == 'WARNING' and warning.trace in row['text'] and 'Runner trace probe' in row['text']
        for row in detail.json()['data']['logs']
    )
    with (runner_e2e_tmpdir / 'langbot.stdout.log').open() as stream:
        assert any(
            row.trace == warning.trace and f'/agents/{agent_uuid}/debug ' in row.msg for row in records(stream, 'core')
        )

    db_path = runner_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            'SELECT status, runner_id FROM agent_run WHERE event_id = ?',
            (result['event_id'],),
        ).fetchone()
        assert run_row == ('completed', QA_RUNNER_ID)

        event_types = {
            row[0]
            for row in conn.execute(
                'SELECT type FROM agent_run_event WHERE run_id = (SELECT run_id FROM agent_run WHERE event_id = ?)',
                (result['event_id'],),
            ).fetchall()
        }
        assert {'state.updated', 'message.completed', 'run.completed'}.issubset(event_types)

        state_row = conn.execute("SELECT value_json FROM runner_state WHERE state_key = 'e2e.echo_count'").fetchone()
        assert state_row is not None
        assert '"count": 1' in state_row[0]
    finally:
        conn.close()


def test_http_bot_plugin_lifecycle(runner_client, runner_e2e_tmpdir):
    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    headers = {'Authorization': f'Bearer {token}'}

    def data(response):
        payload = response.json()
        assert payload['code'] == 0, payload
        return payload['data']

    agent = data(
        client.post(
            '/api/v1/agents',
            headers=headers,
            json={
                'kind': 'agent',
                'name': 'Plugin lifecycle QA',
                'supported_event_patterns': ['message.*'],
                'config': {'runner': {'id': QA_RUNNER_ID}, 'runner_config': {QA_RUNNER_ID: {}}},
            },
        )
    )['uuid']
    pipeline = _create_boundary_pipeline(client, token)
    enabled = {'plugins': {'enable_all': False, 'plugins': [{'author': 'e2e', 'name': 'agent-runner-qa'}]}}

    def route(target, uuid, text, priority, policy):
        return {
            'event_pattern': 'message.received',
            'target_type': target,
            'target_uuid': uuid,
            'priority': priority,
            'policy': policy,
            'filters': [{'field': 'message_text', 'operator': 'contains', 'value': text}] if text else [],
        }

    bot = data(
        client.post(
            '/api/v1/platform/bots',
            headers=headers,
            json={
                'adapter': 'http_bot',
                'name': 'Plugin lifecycle QA',
                'enable': True,
                'adapter_config': {'signature_required': False, 'callback_timeout': 2},
                'event_bindings': [
                    route('discard', '', 'discard-probe', 4, {}),
                    route('pipeline', pipeline, 'disabled', 3, {}),
                    route('agent', agent, 'agent-probe', 2, enabled),
                    route('pipeline', pipeline, '', 1, enabled),
                ],
                'message_policy': {
                    'plugins': {'enable_all': False, 'plugins': []},
                    'trigger': {
                        'group-respond-rules': {'enabled': True, 'at': True, 'prefix': [], 'regexp': [], 'random': 0}
                    },
                },
            },
        )
    )['uuid']

    def send(text, kind='person'):
        reply = data(
            client.post(
                f'/bots/{bot}/sync',
                json={'session_id': 'lifecycle', 'session_type': kind, 'message': [{'type': 'Plain', 'text': text}]},
            )
        )
        return [item['text'] for item in reply['message'] if item.get('type') == 'Plain']

    assert send('/qa_boundary_command query-probe') == ['command:' + bot]
    assert send('group-probe messaging', 'group') == ['group:' + bot]
    assert send('group-probe agent-probe', 'group') == ['group:' + bot]
    assert data(client.get(f'/api/v1/agents/{agent}/runs', headers=headers))['items'] == []
    assert send('no mention', 'group') == []
    assert send('discard-probe disabled') == []
    disabled_command = '/qa_boundary_command query-probe disabled'
    assert send(disabled_command) == ['e2e echo: ' + disabled_command]
    data(client.put(f'/api/v1/platform/bots/{bot}', headers=headers, json={'message_policy': enabled}))
    registrations = data(client.get(f'/api/v1/platform/bots/{bot}/plugin-registrations', headers=headers))['plugins']
    assert 'GroupMessageReceived' in registrations['e2e/agent-runner-qa']['events']
    assert send('discard-probe') == []
    counts = json.loads(send('lifecycle-counts')[0])
    received = counts['received']
    for text in ('group-probe messaging', 'group-probe agent-probe', 'no mention', 'discard-probe', 'lifecycle-counts'):
        assert received.count(text) == 1, received
    assert disabled_command not in received
    assert 'discard-probe disabled' not in received
    assert 'group-probe messaging' not in counts['ran']
    assert 'no mention' not in counts['ran']

    for mode in ('silent', 'notice'):
        data(
            client.put(
                f'/api/v1/platform/bots/{bot}',
                headers=headers,
                json={
                    'command_settings': {
                        'denied_reply': mode,
                        'plugin_permissions': {'e2e/agent-runner-qa/qa_boundary_command': 'admins'},
                    },
                    'message_policy': {**enabled, 'trigger': {'group-respond-rules': {'enabled': False}}},
                },
            )
        )
        for kind in ('person', 'group'):
            for command in ('/status', '/qa_boundary_command query-probe'):
                reply = send(command, kind)
                if mode == 'silent':
                    assert reply == []
                else:
                    assert reply in (['Permission denied'], ['没有执行此操作的权限'])


@pytest.mark.parametrize('kind', ['person', 'group'])
def test_aggregated_messages_reach_plugin_separately(runner_client, runner_e2e_tmpdir, kind):
    from tools.regression.http_bot import signed_headers

    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    pipeline = _create_boundary_pipeline(client, token)
    response = client.post(
        '/api/v1/platform/bots',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'name': 'Aggregation ' + kind,
            'adapter': 'http_bot',
            'enable': True,
            'adapter_config': {'signature_required': True, 'inbound_secret': 'qa-sign', 'callback_timeout': 5},
            'message_policy': {
                'plugins': {'enable_all': True},
                'trigger': {
                    'message-aggregation': {'enabled': True, 'delay': 2},
                    'group-respond-rules': {'enabled': False},
                },
            },
            'event_bindings': [
                {'id': 'chat', 'event_pattern': 'message.received', 'target_type': 'pipeline', 'target_uuid': pipeline}
            ],
        },
    ).json()
    assert response['code'] == 0, response
    bot = response['data']['uuid']

    def send(text, sync=False, session=kind):
        body = json.dumps(
            {'session_type': kind, 'session_id': session, 'message': [{'type': 'Plain', 'text': text}]}
        ).encode()
        reply = client.post(
            f'/bots/{bot}' + ('/sync' if sync else ''), headers=signed_headers(body, 'qa-sign'), content=body
        ).json()
        assert reply['code'] == 0, reply
        return reply['data']

    first, second = [f'{kind}-aggregate-{i}' for i in (1, 2)]
    send(first)
    assert [
        part['text'] for part in send('/qa_boundary_command query-probe', True)['message'] if part['type'] == 'Plain'
    ] == ['command:' + bot]
    send(second)
    deadline = time.monotonic() + 20
    while True:
        reply = send('lifecycle-counts', True, 'counts-' + kind)
        counts = json.loads(next(part['text'] for part in reply['message'] if part['type'] == 'Plain'))
        if any(first in text and second in text for text in counts['ran']):
            break
        assert time.monotonic() < deadline, counts
    for text in (first, second):
        assert counts['received'].count(text) == 1
        assert text not in counts['ran']
    assert not any('qa_boundary_command' in text and first in text for text in counts['ran'])


def test_missing_agent_route_reports_failure(runner_client, runner_e2e_tmpdir):
    from uuid import uuid4
    from tools.regression.http_bot import signed_headers

    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    headers = {'Authorization': 'Bearer ' + token}

    def create(path, payload):
        response = client.post('/api/v1/' + path, headers=headers, json=payload).json()
        assert response['code'] == 0, response
        return response['data']['uuid']

    agent = create(
        'agents',
        {
            'name': 'Missing target',
            'kind': 'agent',
            'supported_event_patterns': ['message.*'],
            'config': {'runner': {'id': QA_RUNNER_ID}, 'runner_config': {QA_RUNNER_ID: {}}},
        },
    )
    bot = create(
        'platform/bots',
        {
            'name': 'Stale route',
            'adapter': 'http_bot',
            'enable': True,
            'adapter_config': {'inbound_secret': 'qa-sign', 'signature_required': True},
            'event_bindings': [{'event_pattern': 'message.received', 'target_type': 'agent', 'target_uuid': agent}],
            'message_policy': {'trigger': {'group-respond-rules': {'enabled': False}}},
        },
    )
    stale = str(uuid4())
    with contextlib.closing(sqlite3.connect(runner_e2e_tmpdir / 'data/langbot.db')) as database:
        with database:
            assert database.execute('UPDATE agents SET uuid=? WHERE uuid=?', (stale, agent)).rowcount == 1
        try:
            for kind in ('person', 'group'):
                body = json.dumps(
                    {
                        'session_type': kind,
                        'session_id': 'missing',
                        'message': [{'type': 'Plain', 'text': 'missing ' + kind}],
                    }
                ).encode()
                reply = client.post('/bots/' + bot, content=body, headers=signed_headers(body, 'qa-sign'))
                assert reply.status_code == 202
                deadline = time.monotonic() + 15
                while True:
                    row = database.execute(
                        "SELECT metadata_json FROM event_log WHERE bot_id=? AND event_type='message.received' AND input_summary=?",
                        (bot, 'missing ' + kind),
                    ).fetchone()
                    metadata = json.loads(row[0]) if row else {}
                    if metadata.get('routes'):
                        break
                    assert time.monotonic() < deadline, metadata
                    time.sleep(0.1)
                assert metadata['status'] == 'failed', metadata
                (route,) = metadata['routes']
                assert (route['target_uuid'], route['failure_code']) == (agent, 'processor_not_found'), route
        finally:
            with database:
                database.execute('UPDATE agents SET uuid=? WHERE uuid=?', (agent, stale))


def test_legacy_chat_config_http(runner_client):
    client = runner_client
    headers = {'Authorization': f'Bearer {_init_and_auth(client)}'}
    legacy = {'config': {'trigger': {}, 'safety': {}}}

    def request(method, path, **kwargs):
        body = client.request(method, '/api/v1/pipelines' + path, headers=headers, **kwargs).json()
        assert body['code'] == 0, body
        return body['data']

    created = request('POST', '', json={'name': 'Legacy settings', **legacy})
    path = '/' + created['uuid']
    updated = request('PUT', path, json=legacy)
    copied = request('POST', path + '/copy', json=legacy)
    for result in [created, updated, copied]:
        assert result['ignored_keys'] == ['safety', 'trigger']
    for ident in [created['uuid'], copied['uuid']]:
        assert not legacy['config'].keys() & request('GET', '/' + ident)['pipeline']['config'].keys()


def test_upgrade_assistant_actions(runner_client, runner_e2e_tmpdir):
    client = runner_client
    token = _init_and_auth(client)
    headers = {'Authorization': f'Bearer {token}'}
    prefix = '/api/v1/platform/bots'
    checks = prefix + '/_/upgrade-checks'

    def request(method, path, **kwargs):
        payload = client.request(method, path, headers=headers, **kwargs).json()
        assert payload['code'] == 0, payload
        return payload['data']

    package_dir = runner_e2e_tmpdir / 'essential-build'
    subprocess.run(
        [sys.executable, '-m', 'langbot_plugin.cli.__init__', 'build', '-o', str(package_dir)],
        cwd=find_project_root() / 'plugins/misc/EssentialCommands',
        check=True,
    )
    (package,) = package_dir.iterdir()
    plugin = 'langbot-team/EssentialCommands'
    _install_qa_plugin(client, token, package, runner_id=plugin)
    pipeline = request('POST', '/api/v1/pipelines', json={'name': 'Upgrade assistant'})['uuid']
    bot = request(
        'POST',
        prefix,
        json={
            'name': 'Upgrade assistant',
            'adapter': 'http_bot',
            'enable': False,
            'adapter_config': {},
            'message_policy': {
                'plugins': {'enable_all': False, 'plugins': [{'author': 'langbot-team', 'name': 'EssentialCommands'}]}
            },
            'event_bindings': [
                {
                    'id': 'chat',
                    'event_pattern': 'message.received',
                    'target_type': 'pipeline',
                    'target_uuid': pipeline,
                    'policy': {'output': {'misc': {'at-sender': True}}},
                }
            ],
        },
    )['uuid']
    database = runner_e2e_tmpdir / 'data/langbot.db'
    with contextlib.closing(sqlite3.connect(database)) as connection, connection:
        (workspace,) = connection.execute('SELECT workspace_uuid FROM bots WHERE uuid=?', (bot,)).fetchone()
        for stage, report in {
            '0059': {'route_overrides': [{'bot_uuid': bot, 'route_id': 'chat', 'chat_uuid': pipeline}]},
            '0060': {'enabled_plugins': {bot: {plugin: [None]}}},
            'commands': {'original_prefixes': ['!']},
        }.items():
            connection.execute(
                'INSERT INTO workspace_metadata (workspace_uuid,key,value) VALUES (?,?,?) '
                'ON CONFLICT(workspace_uuid,key) DO UPDATE SET value=excluded.value',
                (workspace, 'message_policy_upgrade:' + stage, json.dumps(report)),
            )

    def items():
        return {
            item['code']: item for item in request('GET', checks)['items'] if item['params'].get('bot_uuid', bot) == bot
        }

    deadline = time.monotonic() + 30
    while True:
        original = items()
        if 'help' in original.get('plugin_command_collision', {}).get('params', {}).get('names', []):
            break
        if time.monotonic() >= deadline:
            pytest.fail('EssentialCommands did not register help')
        time.sleep(0.25)
    assert set(original) == {
        'command_prefix_changed',
        'command_admin_missing',
        'command_plugin_enabled',
        'plugin_command_collision',
        'equivalent_route_policies',
        'chat_settings_moved',
    }
    assert original['plugin_command_collision']['params']['essential_installed']
    request('POST', checks + '/confirm', json={'id': original['command_admin_missing']['id']})
    assert {code for code, item in items().items() if item['confirmed']} == {'command_admin_missing'}
    request('POST', checks + '/confirm-all')
    assert all(item['confirmed'] for item in items().values())
    with contextlib.closing(sqlite3.connect(database)) as connection:
        (saved,) = connection.execute(
            'SELECT value FROM workspace_metadata WHERE workspace_uuid=? AND key=?',
            (workspace, 'message_policy_upgrade:confirmed'),
        ).fetchone()
        assert {item['id'] for item in original.values()} <= set(json.loads(saved))
    for code, action in [
        ('command_prefix_changed', 'restore_prefixes'),
        ('equivalent_route_policies', 'promote_route_policy'),
        ('command_plugin_enabled', 'remove_plugin'),
        ('plugin_command_collision', 'uninstall_essential'),
    ]:
        result = request('POST', checks + '/action', json={'id': original[code]['id'], 'action': action})
        if action == 'uninstall_essential':
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                task = request('GET', f'/api/v1/system/tasks/{result["task_id"]}')['runtime']
                if task['done']:
                    assert task['exception'] is None
                    break
                time.sleep(0.2)
            else:
                pytest.fail('EssentialCommands uninstall did not complete')
        assert code not in items()
    stored = request('GET', prefix + '/' + bot)['bot']
    assert {'!', '！'} <= set(stored['command_settings']['prefixes'])
    assert stored['message_policy']['plugins']['plugins'] == []
    assert stored['message_policy']['output']['misc']['at-sender'] is True


def test_http_bot_builtin_commands(runner_client, runner_e2e_tmpdir):
    client = runner_client
    token = _init_and_auth(client)
    headers = {'Authorization': f'Bearer {token}'}

    def data(response):
        body = response.json()
        assert body['code'] == 0, body
        return body['data']

    data(client.put('/api/v1/workspaces/current/language', headers=headers, json={'language': 'zh_Hans'}))
    pipeline = data(client.post('/api/v1/pipelines', headers=headers, json={'name': 'QA Chat'}))['uuid']
    catalog = data(client.get('/api/v1/platform/bots/_/builtin-commands', headers=headers))['commands']
    assert len(catalog) == 12
    print('catalog:', catalog[0])
    settings = {'denied_reply': 'silent', 'builtin': {}, 'plugin_permissions': {}}
    bot = data(
        client.post(
            '/api/v1/platform/bots',
            headers=headers,
            json={
                'adapter': 'http_bot',
                'name': 'QA Bot',
                'enable': True,
                'command_settings': settings,
                'message_policy': {'trigger': {'group-respond-rules': {'enabled': False}}},
                'adapter_config': {'signature_required': False, 'callback_timeout': 2},
                'event_bindings': [
                    {
                        'event_pattern': 'message.received',
                        'target_type': 'pipeline',
                        'target_uuid': pipeline,
                        'filters': [{'field': 'message_text', 'operator': 'contains', 'value': '/new'}],
                    }
                ],
            },
        )
    )['uuid']
    url = f'/api/v1/platform/bots/{bot}'
    stored = data(client.get(url, headers=headers))['bot']['command_settings']
    data(client.post(f'{url}/admins', headers=headers, json={'launcher_type': 'person', 'launcher_id': 'admin'}))
    legacy = client.put(url, headers=headers, json={'command_settings': {**stored, 'admins': ['person_user']}})
    assert legacy.status_code == 200
    data(legacy)
    assert 'admins' not in data(client.get(url, headers=headers))['bot']['command_settings']

    def send(command, sender, group=None):
        response = data(
            client.post(
                f'/bots/{bot}/sync',
                json={
                    'session_id': group or sender,
                    'session_type': 'group' if group else 'person',
                    'sender': {'id': sender},
                    'message': [{'type': 'Plain', 'text': command}],
                },
            )
        )
        text = '\n'.join(part['text'] for part in response['message'] if part.get('type') == 'Plain')
        print(sender, command, repr(text))
        return text

    assert '/help — 列出可用命令' in send('/help', 'user')
    assert 'person_user' in send('/whoami', 'user')
    assert '已开始新会话' in send('/new', 'user')
    assert '机器人：QA Bot' in send('/status', 'admin')
    assert '机器人：QA Bot' in send('/status', 'admin', 'qa-group')
    assert send('/status', 'user', 'qa-group') == ''
    data(client.put(url, headers=headers, json={'command_settings': {'denied_reply': 'notice'}}))
    assert send('/status', 'user', 'qa-group') == '没有执行此操作的权限'

    data(
        client.put(
            url,
            headers=headers,
            json={'command_settings': {'prefixes': ['/', '!'], 'builtin': {'model': {'enabled': True}}}},
        )
    )
    no_route = '当前没有处理这条消息的处理器'
    for group in (None, 'qa-group'):
        assert 'Token 数：' in send('!usage', 'admin', group)
        assert 'LangBot ' in send('!version', 'admin', group)
        assert send('!plugins', 'admin', group)
        for command in ('model', 'tools', 'stop', 'retry', 'undo'):
            assert send('!' + command, 'admin', group) == no_route
        assert send('!version', 'user', group) == '没有执行此操作的权限'


@pytest.mark.parametrize('kind', ['person', 'group'])
def test_agent_stream_policy_callbacks(runner_client, runner_e2e_tmpdir, kind):
    from datetime import datetime
    from tools.regression.http_bot import signed_headers
    from tools.regression.regression_lifecycle_cases import CallbackReceiver

    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    headers = {'Authorization': f'Bearer {token}'}

    def create(path, payload):
        reply = client.post('/api/v1/' + path, headers=headers, json=payload).json()
        assert reply['code'] == 0, reply
        return reply['data']['uuid']

    agent = create(
        'agents',
        {
            'kind': 'agent',
            'name': 'Streaming QA',
            'supported_event_patterns': ['message.*'],
            'config': {
                'runner': {'id': QA_RUNNER_ID},
                'runner_config': {QA_RUNNER_ID: {}},
                'allowed_platform_tools': ['event_reply', 'platform_send_message'],
            },
        },
    )
    with CallbackReceiver('qa-sign') as receiver:
        bot = create(
            'platform/bots',
            {
                'name': 'Streaming QA',
                'adapter': 'http_bot',
                'enable': True,
                'adapter_config': {
                    'signature_required': True,
                    'inbound_secret': 'qa-sign',
                    'callback_url': receiver.url,
                },
                'message_policy': {
                    'trigger': {'group-respond-rules': {'enabled': False}},
                    'output': {
                        'long-text-processing': {'threshold': 2, 'strategy': 'forward'},
                        'force-delay': {'min': 1, 'max': 1},
                        'misc': {'at-sender': True, 'quote-origin': True},
                    },
                },
                'event_bindings': [{'event_pattern': 'message.received', 'target_type': 'agent', 'target_uuid': agent}],
            },
        )
        body = json.dumps(
            {
                'session_type': kind,
                'session_id': 'stream',
                'sender': {'id': 'user'},
                'message': [{'type': 'Plain', 'text': 'stream-policy-probe'}],
            }
        ).encode()
        reply = client.post('/bots/' + bot, content=body, headers=signed_headers(body, 'qa-sign')).json()
        assert reply['code'] == 0, reply
        records = receiver.wait_final(reply['data']['accepted_message_id'], 30)
        chunks = [record['payload'] for record in records if record['status'] == 200]
        sent = receiver.wait_final('', 10)[-1]['payload']
        assert sent['session_id'] == 'qa-notifications' and not sent['stream']
        assert [(part['type'], part['text']) for part in sent['message']] == [('Plain', 'proactive text')]
        delay = datetime.fromisoformat(chunks[0]['timestamp']) - datetime.fromisoformat(sent['timestamp'])
        assert delay.total_seconds() >= 1
        assert [chunk['is_final'] for chunk in chunks] == [False, False, True]
        assert all(chunk['stream'] for chunk in chunks)
        assert [[part['text'] for part in chunk['message'] if part['type'] == 'Plain'] for chunk in chunks] == [
            ['first'],
            ['first and last'],
            ['first and last'],
        ]
        for chunk in chunks:
            assert [part['type'] for part in chunk['message']] == (['At', 'Plain'] if kind == 'group' else ['Plain'])


def test_http_agent_message_policy(runner_client, runner_e2e_tmpdir):
    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    headers = {'Authorization': f'Bearer {token}'}

    def data(response):
        body = response.json()
        assert body['code'] == 0, body
        return body['data']

    agent = data(
        client.post(
            '/api/v1/agents',
            headers=headers,
            json={
                'kind': 'agent',
                'name': 'Agent policy QA',
                'supported_event_patterns': ['message.*'],
                'config': {'runner': {'id': QA_RUNNER_ID}, 'runner_config': {QA_RUNNER_ID: {}}},
            },
        )
    )['uuid']
    bot = data(
        client.post(
            '/api/v1/platform/bots',
            headers=headers,
            json={
                'adapter': 'http_bot',
                'name': 'Agent policy QA',
                'enable': True,
                'adapter_config': {'signature_required': False, 'callback_timeout': 8},
                'event_bindings': [{'event_pattern': 'message.received', 'target_type': 'agent', 'target_uuid': agent}],
                'message_policy': {
                    'plugins': {'enable_all': False, 'plugins': [{'author': 'e2e', 'name': 'agent-runner-qa'}]},
                    'trigger': {'group-respond-rules': {'enabled': True, 'prefix': [], 'random': 0, 'at': True}},
                },
            },
        )
    )['uuid']

    def send(text, kind='person'):
        result = data(
            client.post(
                f'/bots/{bot}/sync',
                json={'session_id': 'agent-policy', 'session_type': kind, 'message': [{'type': 'Plain', 'text': text}]},
            )
        )
        return [part['text'] for part in result['message'] if part['type'] == 'Plain']

    assert send('agent-probe intercept') == ['handled before agent']
    assert send('agent-probe blocked', 'group') == []
    assert data(client.get(f'/api/v1/agents/{agent}/runs', headers=headers))['items'] == []
    assert send('agent-probe replace-output') == ['updated output']
    assert send('agent-probe replace-input') == ['e2e echo: updated input']


@pytest.mark.parametrize('kind', ['person', 'group'])
def test_subscription_replies_after_primary_denial(runner_client, runner_e2e_tmpdir, kind):
    from tools.regression.http_bot import signed_headers

    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    headers = {'Authorization': f'Bearer {token}'}

    def create(path, payload):
        result = client.post('/api/v1/' + path, headers=headers, json=payload).json()
        assert result['code'] == 0, result
        return result['data']['uuid']

    agent = create(
        'agents',
        {
            'name': 'Primary',
            'kind': 'agent',
            'supported_event_patterns': ['message.*'],
            'config': {'runner': {'id': QA_RUNNER_ID}, 'runner_config': {QA_RUNNER_ID: {}}},
        },
    )
    processor = create(
        'agents',
        {
            'name': 'Subscriber',
            'kind': 'event_processor',
            'component_ref': 'plugin:e2e/agent-runner-qa/welcome',
            'parameters': {'greeting': 'subscriber reply'},
        },
    )
    bot = create(
        'platform/bots',
        {
            'name': 'Subscription QA',
            'adapter': 'http_bot',
            'enable': True,
            'adapter_config': {'signature_required': True, 'inbound_secret': 'qa-sign', 'callback_timeout': 3},
            'plugin_processors': [{'processor_uuid': processor}],
            'event_bindings': [{'event_pattern': 'message.received', 'target_type': 'agent', 'target_uuid': agent}],
            'message_policy': {
                'trigger': {'ignore-rules': {'prefix': ['skip:']}, 'group-respond-rules': {'enabled': False}},
                'output': {'misc': {'at-sender': True}},
            },
        },
    )
    for text, expected, code in [
        ('skip: probe', 'ignored', 'message_policy'),
        ('/status', 'completed', 'command_permission_denied'),
    ]:
        body = json.dumps(
            {
                'session_id': kind,
                'session_type': kind,
                'sender': {'id': 'tester'},
                'message': [{'type': 'Plain', 'text': text}],
            }
        ).encode()
        result = client.post(f'/bots/{bot}/sync', content=body, headers=signed_headers(body, 'qa-sign')).json()
        assert result['code'] == 0, result
        parts = result['data']['message']
        assert [part['type'] for part in parts] == (['At', 'Plain'] if kind == 'group' else ['Plain'])
        assert parts[-1]['text'] == 'subscriber reply'
        with contextlib.closing(sqlite3.connect(runner_e2e_tmpdir / 'data/langbot.db')) as database:
            row = database.execute(
                "SELECT metadata_json FROM event_log WHERE bot_id=? AND event_type='message.received' ORDER BY id DESC LIMIT 1",
                (bot,),
            ).fetchone()
        metadata = json.loads(row[0])
        assert metadata['status'] == expected, metadata
        primary, subscription = metadata['routes']
        assert primary['failure_code'] == code
        assert subscription['target_uuid'] == processor and subscription['status'] == 'delivered'
        assert client.get(f'/api/v1/agents/{agent}/runs', headers=headers).json()['data']['items'] == []


@pytest.mark.parametrize('kind', ['person', 'group'])
def test_command_rate_limit_window(runner_client, runner_e2e_tmpdir, kind):
    from concurrent.futures import ThreadPoolExecutor
    from tools.regression.http_bot import signed_headers

    client = runner_client
    headers = {'Authorization': 'Bearer ' + _init_and_auth(client)}
    window = 8
    result = client.post(
        '/api/v1/platform/bots',
        headers=headers,
        json={
            'name': 'Rate QA',
            'adapter': 'http_bot',
            'enable': True,
            'adapter_config': {'signature_required': True, 'inbound_secret': 'qa-sign'},
            'message_policy': {
                'trigger': {'group-respond-rules': {'enabled': False}},
                'safety': {
                    'rate-limit': {'enabled': True, 'strategy': 'drop', 'window-length': window, 'limitation': 2}
                },
            },
        },
    ).json()
    assert result['code'] == 0, result
    bot = result['data']['uuid']

    def send(index):
        body = json.dumps(
            {'session_type': kind, 'session_id': 'rate', 'message': [{'type': 'Plain', 'text': f'/whoami {index}'}]}
        ).encode()
        reply = client.post('/bots/' + bot, content=body, headers=signed_headers(body, 'qa-sign'))
        assert reply.status_code == 202, reply.text

    def routes(count):
        end = time.monotonic() + 12
        with contextlib.closing(sqlite3.connect(runner_e2e_tmpdir / 'data/langbot.db')) as database:
            while True:
                records = [
                    json.loads(row[0]).get('routes')
                    for row in database.execute(
                        "SELECT metadata_json FROM event_log WHERE bot_id=? AND event_type='message.received' ORDER BY id",
                        (bot,),
                    )
                ]
                if len(records) == count and all(records):
                    return [record[0] for record in records]
                assert time.monotonic() < end, records
                time.sleep(0.1)

    time.sleep(window - time.time() % window + 0.05)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(send, range(3)))
    burst = routes(3)
    assert sum(route['status'] == 'delivered' for route in burst) == 2, burst
    assert [route['policy_item'] for route in burst if route['status'] == 'discarded'] == ['rate-limit']
    time.sleep(window - time.time() % window + 0.05)
    send(3)
    assert routes(4)[-1]['status'] == 'delivered'


def test_event_processor_real_runtime_logs_actions_and_instance_isolation(
    runner_client,
    runner_e2e_tmpdir,
):
    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    headers = {'Authorization': f'Bearer {token}'}
    metadata_response = client.get('/api/v1/agents/_/metadata', headers=headers).json()
    assert metadata_response['code'] == 0, metadata_response
    metadata = metadata_response['data']
    ref = 'plugin:e2e/agent-runner-qa/welcome'
    assert any(item['id'] == ref for item in metadata['event_processors']), metadata
    assert ref not in _wait_for_qa_runner(client, token)
    created = []
    for name in ('First', 'Second'):
        response = client.post(
            '/api/v1/agents',
            headers=headers,
            json={
                'kind': 'event_processor',
                'name': name,
                'component_ref': ref,
                'parameters': {'greeting': name},
            },
        ).json()
        assert response['code'] == 0, response
        created.append(response['data']['uuid'])
    for processor_id in created:
        page = client.get(f'/api/v1/agents/{processor_id}/runs', headers=headers).json()
        assert page['data']['items'] == [], page
    result = client.post(
        f'/api/v1/agents/{created[0]}/debug',
        headers=headers,
        json={
            'event_type': 'group.member_joined',
            'data': {'member': {'id': 'member-1', 'nickname': 'Tester'}, 'group': {'id': 'group-1'}},
        },
    ).json()
    assert result['code'] == 0, result
    logs = [event['data']['text'] for event in result['data']['execution_events'] if event['type'] == 'processor.log']
    assert logs == ['Handling member-1', 'Reply simulated: True'], result
    actions = [event for event in result['data']['execution_events'] if event['type'] == 'tool.call.completed']
    assert len(actions) == 1, result
    assert actions[0]['data']['tool_name'] == 'event_reply'
    assert actions[0]['data']['result']['mock'] is True
    assert result['data']['final_text'] == '', result
    page = client.get(f'/api/v1/agents/{created[0]}/runs', headers=headers).json()['data']
    assert len(page['items']) == 1, page
    run = page['items'][0]
    assert run['status'] == 'completed', run
    assert run['metadata']['input_event']['member']['id'] == 'member-1'
    trace = client.get(f'/api/v1/agents/{created[0]}/runs/{run["run_id"]}/events', headers=headers).json()
    assert trace['code'] == 0, trace
    assert any(item['type'] == 'processor.log' for item in trace['data']['items']), trace
    foreign = client.get(f'/api/v1/agents/{created[1]}/runs/{run["run_id"]}/events', headers=headers)
    assert foreign.status_code == 400
    assert client.get(f'/api/v1/agents/{created[1]}/runs', headers=headers).json()['data']['items'] == []


def _create_boundary_pipeline(client, token):
    headers = {'Authorization': f'Bearer {token}'}
    created = client.post(
        '/api/v1/pipelines', headers=headers, json={'name': 'Runner boundary QA', 'description': ''}
    ).json()
    assert created['code'] == 0, created
    pipeline_id = created['data']['uuid']
    config = client.get(f'/api/v1/pipelines/{pipeline_id}', headers=headers).json()['data']['pipeline']['config']
    config['ai']['runner'] = {'id': QA_RUNNER_ID, 'expire-time': 0}
    config['ai']['runner_config'] = {QA_RUNNER_ID: {'prefix': 'e2e echo', 'hidden': {'keep': [None, False, '  raw  ']}}}
    saved = client.put(f'/api/v1/pipelines/{pipeline_id}', headers=headers, json={'config': config}).json()
    assert saved['code'] == 0, saved
    return pipeline_id


def test_dashboard_chat_uses_neutral_policy(runner_client, runner_e2e_tmpdir):
    from websockets.sync.client import connect

    from tools.regression.http_bot import signed_headers

    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    pipeline = _create_boundary_pipeline(client, token)
    created = client.post(
        '/api/v1/platform/bots',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'name': 'Debug policy comparison',
            'adapter': 'http_bot',
            'enable': True,
            'adapter_config': {'signature_required': True, 'inbound_secret': 'qa-sign', 'callback_timeout': 3},
            'event_bindings': [
                {'id': 'chat', 'event_pattern': 'message.received', 'target_type': 'pipeline', 'target_uuid': pipeline}
            ],
            'message_policy': {
                'trigger': {'group-respond-rules': {'enabled': False}, 'ignore-rules': {'prefix': ['ignored:']}},
                'output': {
                    'long-text-processing': {'strategy': 'forward', 'threshold': 8},
                    'misc': {'at-sender': False, 'quote-origin': True},
                },
            },
        },
    ).json()
    assert created['code'] == 0, created
    bot = created['data']['uuid']
    with contextlib.closing(sqlite3.connect(runner_e2e_tmpdir / 'data/langbot.db')) as db:
        (workspace,) = db.execute('SELECT workspace_uuid FROM bots WHERE uuid=?', (bot,)).fetchone()
        for kind in ('person', 'group'):
            uri = f'ws://127.0.0.1:{client.base_url.port}/api/v1/pipelines/{pipeline}/ws/connect?session_type={kind}'
            with connect(uri, origin=str(client.base_url).rstrip('/'), proxy=None) as dashboard:
                dashboard.send(json.dumps({'type': 'authenticate', 'token': token, 'workspace_uuid': workspace}))
                assert json.loads(dashboard.recv(timeout=10))['type'] == 'connected'
                for text in [f'ignored: {kind}', f'normal {kind}']:
                    chain = [{'type': 'Plain', 'text': text}]
                    body = json.dumps({'session_type': kind, 'session_id': 'policy', 'message': chain}).encode()
                    reply = client.post(
                        f'/bots/{bot}/sync', headers=signed_headers(body, 'qa-sign'), content=body
                    ).json()
                    assert reply['code'] == 0, reply
                    parts = reply['data']['message']
                    row = db.execute(
                        'SELECT metadata_json FROM event_log WHERE bot_id=? AND event_id=?',
                        (bot, f'platform:{bot}:{reply["data"]["reply_to"]}'),
                    ).fetchone()
                    metadata = json.loads(row[0])
                    if text.startswith('ignored:'):
                        assert not parts and (metadata['status'], metadata['policy_item']) == (
                            'ignored',
                            'ignore-rules',
                        ), metadata
                    else:
                        assert [part['type'] for part in parts] == ['Forward'], (parts, metadata)
                        actions = [
                            action for event in metadata.get('policy_events', []) for action in event.get('actions', [])
                        ]
                        assert {'kind': 'quote'} in actions and {
                            'kind': 'long_text',
                            'strategy': 'forward',
                        } in actions, metadata

                    dashboard.send(json.dumps({'type': 'message', 'message': chain, 'stream': False}))
                    frame = json.loads(dashboard.recv(timeout=20))
                    assert frame['type'] == 'user_message', frame
                    frame = json.loads(dashboard.recv(timeout=20))
                    assert frame['type'] == 'response', frame
                    assert frame['data']['message_chain'] == [{'type': 'Plain', 'text': f'e2e echo: {text}'}], frame


def test_onebot_native_quote(runner_client, runner_e2e_tmpdir):
    from websockets.sync.client import connect

    from tests.unit_tests.platform.onebot_mock import OneBotMock

    client = runner_client
    token = _init_and_auth(client)
    _ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')

    def create(path, payload):
        result = client.post('/api/v1/' + path, headers={'Authorization': 'Bearer ' + token}, json=payload).json()
        assert result['code'] == 0, result
        return result['data']['uuid']

    chat = _create_boundary_pipeline(client, token)
    agent = create(
        'agents',
        {
            'kind': 'agent',
            'name': 'Quote QA',
            'supported_event_patterns': ['message.*'],
            'config': {'runner': {'id': QA_RUNNER_ID}, 'runner_config': {QA_RUNNER_ID: {}}},
        },
    )
    peer = OneBotMock()
    message_id = 7000
    for route, target in [('pipeline', chat), ('agent', agent)]:
        for quote in (False, True):
            bot = create(
                'platform/bots',
                {
                    'name': f'Quote {route} {quote}',
                    'adapter': 'onebot-v11',
                    'enable': True,
                    'adapter_config': {'connection_mode': 'reverse_ws', 'access-token': 'onebot-qa', 'self_id': '42'},
                    'message_policy': {
                        'trigger': {'group-respond-rules': {'enabled': False}},
                        'output': {'misc': {'at-sender': False, 'quote-origin': quote}},
                    },
                    'event_bindings': [
                        {
                            'id': 'reply',
                            'event_pattern': 'message.received',
                            'target_type': route,
                            'target_uuid': target,
                        }
                    ],
                },
            )
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
                    for text in ['echo', '/whoami'] if route == 'pipeline' else ['echo']:
                        message_id += 1
                        incoming = peer.message(
                            kind,
                            'friend' if kind == 'private' else 'normal',
                            [{'type': 'text', 'data': {'text': text}}],
                        )
                        socket_peer.send(
                            json.dumps(
                                incoming | {'message_id': message_id, 'raw_message': text, 'time': int(time.time())}
                            )
                        )
                        deadline = time.monotonic() + 30
                        while True:
                            request = json.loads(socket_peer.recv(timeout=max(0, deadline - time.monotonic())))
                            socket_peer.send(json.dumps(peer.handle(request) | {'echo': request['echo']}))
                            if request['action'] in ('send_msg', 'send_private_msg', 'send_group_msg'):
                                break
                        parts = request['params']['message']
                        assert [str(part['data']['id']) for part in parts if part['type'] == 'reply'] == (
                            [str(message_id)] if quote else []
                        ), (route, kind, text, request)
                        reply = ''.join(part['data']['text'] for part in parts if part['type'] == 'text')
                        assert '10001' in reply if text == '/whoami' else reply == 'e2e echo: echo', request
                        with contextlib.closing(sqlite3.connect(runner_e2e_tmpdir / 'data/langbot.db')) as db:
                            row = db.execute(
                                'SELECT metadata_json FROM event_log WHERE event_id=? AND bot_id=?',
                                (f'platform:{bot}:{message_id}', bot),
                            ).fetchone()
                        assert row, (bot, message_id)
                        actions = [
                            action
                            for event in json.loads(row[0]).get('policy_events', [])
                            for action in event.get('actions', [])
                        ]
                        assert ({'kind': 'quote'} in actions) == quote, row


def _pipeline_failure_diagnostics(directory, pipeline_id):
    with contextlib.closing(sqlite3.connect(directory / 'data' / 'langbot.db')) as connection:
        messages = connection.execute(
            'SELECT status, level, runner_name FROM monitoring_messages WHERE pipeline_id = ?',
            (pipeline_id,),
        ).fetchall()
        calls = connection.execute(
            'SELECT status, error_message FROM monitoring_llm_calls WHERE pipeline_id = ?',
            (pipeline_id,),
        ).fetchall()
        runs = connection.execute(
            'SELECT status, status_reason FROM agent_run WHERE binding_id = ?',
            (pipeline_id,),
        ).fetchall()
        errors = connection.execute(
            'SELECT error_type, error_message, stack_trace FROM monitoring_errors WHERE pipeline_id = ?',
            (pipeline_id,),
        ).fetchall()
    diagnostic = {'messages': messages, 'calls': calls, 'runs': runs, 'errors': errors}
    target = find_project_root() / '.qa' / 'lang54' / 'pipeline-failure.json'
    target.write_text(json.dumps(diagnostic, indent=2), encoding='utf-8')
    return diagnostic


def test_mixed_plugin_runner_does_not_authorize_extensions(runner_client, runner_e2e_tmpdir):
    token = _init_and_auth(runner_client)
    _ensure_qa_plugin(runner_client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    pipeline_id = _create_boundary_pipeline(runner_client, token)
    headers = {'Authorization': f'Bearer {token}'}

    def run(text):
        response = runner_client.post(
            f'/api/v1/pipelines/{pipeline_id}/run', headers=headers, json={'message': text}
        ).json()
        assert response['code'] == 0, response
        if response['data']['status'] != 'completed':
            pytest.fail(
                f'{response}\nPersisted diagnostics: {_pipeline_failure_diagnostics(runner_e2e_tmpdir, pipeline_id)}'
            )
        return response['data']['reply']

    enabled = json.loads(run('boundary probe enabled'))
    assert enabled['listener_hits'] > 0, enabled
    assert any('qa_boundary_tool' in name for name in enabled['tool_names']), enabled
    assert enabled['tool_denied'] is False, enabled
    assert run('/qa_boundary_command') == 'e2e echo: /qa_boundary_command'
    last_enabled = json.loads(run('boundary probe before disabling'))
    disabled = runner_client.put(
        f'/api/v1/pipelines/{pipeline_id}/extensions',
        headers=headers,
        json={
            'enable_all_plugins': False,
            'bound_plugins': [],
            'enable_all_mcp_servers': False,
            'bound_mcp_servers': [],
            'enable_all_skills': False,
            'bound_skills': [],
        },
    ).json()
    assert disabled['code'] == 0, disabled
    restricted = json.loads(run('boundary probe disabled'))
    assert restricted['listener_hits'] == last_enabled['listener_hits'], restricted
    assert not any('qa_boundary_tool' in name for name in restricted['tool_names']), restricted
    assert restricted['tool_denied'] is True, restricted
    assert run('/qa_boundary_command') == 'e2e echo: /qa_boundary_command'


def test_chromium_pipeline_save_copy_execute_real_runtime(runner_client, runner_e2e_tmpdir):
    token = _init_and_auth(runner_client)
    _ensure_qa_plugin(runner_client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    pipeline_id = _create_boundary_pipeline(runner_client, token)
    headers = {'Authorization': f'Bearer {token}'}
    response = runner_client.put(
        f'/api/v1/pipelines/{pipeline_id}/extensions',
        headers=headers,
        json={
            'enable_all_plugins': False,
            'bound_plugins': [],
            'enable_all_mcp_servers': False,
            'bound_mcp_servers': [],
            'enable_all_skills': False,
            'bound_skills': [],
        },
    ).json()
    assert response['code'] == 0, response
    env = os.environ.copy()
    env.update(
        {
            'LANGBOT_RUNNER_API_URL': str(runner_client.base_url).rstrip('/'),
            'LANGBOT_RUNNER_WEB_PORT': str(_free_port()),
            'LANGBOT_RUNNER_TOKEN': token,
            'LANGBOT_RUNNER_PIPELINE_ID': pipeline_id,
            'LANGBOT_RUNNER_BROWSER_OUTPUT': str(runner_e2e_tmpdir / 'browser-results'),
        }
    )
    browser = subprocess.Popen(
        ['node', 'node_modules/@playwright/test/cli.js', 'test', '--config=playwright.runner-runtime.config.ts'],
        cwd=find_project_root() / 'web',
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = browser.communicate(timeout=300)
        assert browser.returncode == 0, f'Chromium real-stack E2E:\n{stdout}\n{stderr}'
        print(stdout)
    finally:
        try:
            os.killpg(browser.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(browser.pid, signal.SIGKILL)
            browser.wait(timeout=5)
