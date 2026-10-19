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
            from pathlib import Path

            from langbot_plugin.api.definition.components.runner.runner import Runner
            from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
            from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
            from langbot_plugin.api.entities.builtin.provider.message import Message


            class DefaultRunner(Runner):
                async def run(self, ctx: RunnerContext) -> AsyncGenerator[RunnerResult, None]:
                    text = ctx.input.to_text()
                    content = f'{ctx.config.get("prefix", "e2e echo")}: {text}'
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

            class BoundaryCommand(Command):
                async def initialize(self):
                    await super().initialize()
                    @self.subcommand('')
                    async def handle(self, ctx):
                        yield CommandReturn(text='QA_COMMAND_EXECUTED')
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

            class BoundaryListener(EventListener):
                async def initialize(self):
                    await super().initialize()
                    @self.handler(events.PersonNormalMessageReceived)
                    async def handle(ctx):
                        self.plugin.boundary_listener_hits = getattr(self.plugin, 'boundary_listener_hits', 0) + 1
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
          events: [group.member_joined]
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
        from langbot_plugin.api.entities.builtin.platform.events import MemberJoinedEvent

        class WelcomeProcessor(Runner):
            async def initialize(self):
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
        if path.stem != 'websocket'
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


def _install_qa_plugin(client: httpx.Client, token: str, package_path: Path) -> None:
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
            assert task['task_context']['metadata']['progress_percent'] == 100
            return
        time.sleep(1)
    raise AssertionError(f'Plugin installation task {task_id} did not complete')


def _wait_for_qa_runner(client: httpx.Client, token: str, timeout: float = 60) -> set[str]:
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
        option_names = {option['name'] for option in runner_select['options']}
        if QA_RUNNER_ID in option_names:
            break
        time.sleep(1)
    return option_names


def _ensure_qa_plugin(client: httpx.Client, token: str, package_path: Path) -> None:
    if QA_RUNNER_ID in _wait_for_qa_runner(client, token, timeout=2):
        return
    _install_qa_plugin(client, token, package_path)


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


def _pipeline_failure_diagnostics(directory, pipeline_id):
    with sqlite3.connect(directory / 'data' / 'langbot.db') as connection:
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
    assert 'QA_COMMAND_EXECUTED' in run('!qa_boundary_command')
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
    command_reply = run('!qa_boundary_command')
    assert 'QA_COMMAND_EXECUTED' not in command_reply
    assert 'qa_boundary_command' in command_reply


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
