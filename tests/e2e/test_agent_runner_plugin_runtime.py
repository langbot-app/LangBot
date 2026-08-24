"""E2E tests for pluginized AgentRunner execution.

This module starts the real LangBot backend with the plugin system enabled and
loads a deterministic AgentRunner plugin through the real SDK Plugin Runtime.
"""

from __future__ import annotations

import shutil
import socket
import sqlite3
import subprocess
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
QA_PLUGIN_DIRNAME = 'e2e__agent-runner-qa'


@pytest.fixture(scope='session')
def agent_runner_e2e_port():
    """Port for the AgentRunner plugin-runtime E2E process."""
    return 15310


@pytest.fixture(scope='session')
def agent_runner_e2e_tmpdir():
    """Create temporary directory for AgentRunner E2E testing."""
    tmpdir = Path(tempfile.mkdtemp(prefix='langbot_agent_runner_e2e_'))
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _write_qa_agent_runner_plugin(plugin_root: Path) -> None:
    """Write a deterministic AgentRunner plugin used by this E2E."""
    runner_dir = plugin_root / 'components' / 'agent_runner'
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
                en_US: AgentRunner QA
                zh_Hans: AgentRunner QA
              description:
                en_US: Deterministic AgentRunner E2E probe.
                zh_Hans: 确定性的 AgentRunner E2E 探针。
              icon: assets/icon.svg
            spec:
              version: 0.1.0
              config: []
              components:
                AgentRunner:
                  fromDirs:
                    - path: components/agent_runner/
              pages: []
            execution:
              python:
                path: main.py
                attr: AgentRunnerQAPlugin
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


            class AgentRunnerQAPlugin(BasePlugin):
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
            kind: AgentRunner
            metadata:
              name: default
              label:
                en_US: QA Echo Runner
                zh_Hans: QA Echo Runner
              description:
                en_US: Echoes input and exercises run-scoped state APIs.
                zh_Hans: 回显输入并验证运行级状态 API。
            spec:
              config: []
              capabilities:
                streaming: false
              permissions: {}
            execution:
              python:
                path: default.py
                attr: DefaultAgentRunner
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

            from langbot_plugin.api.definition.components.agent_runner.runner import AgentRunner
            from langbot_plugin.api.entities.builtin.agent_runner.context import AgentRunContext
            from langbot_plugin.api.entities.builtin.agent_runner.result import AgentRunResult
            from langbot_plugin.api.entities.builtin.provider.message import Message


            class DefaultAgentRunner(AgentRunner):
                async def run(self, ctx: AgentRunContext) -> AsyncGenerator[AgentRunResult, None]:
                    text = ctx.input.to_text()
                    yield AgentRunResult.message_completed(
                        ctx.run_id,
                        Message(role='assistant', content=f'e2e echo: {text}'),
                    )
                    yield AgentRunResult.state_updated(
                        ctx.run_id,
                        'e2e.echo_count',
                        {'count': 1},
                        scope='conversation',
                    )
                    yield AgentRunResult.run_completed(ctx.run_id, finish_reason='stop')
            """
        ).strip()
        + '\n',
        encoding='utf-8',
    )


def _free_port() -> int:
    """Reserve a currently-free localhost TCP port for this E2E process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope='session')
def agent_runner_runtime_ports():
    """Control/debug ports for the standalone plugin runtime."""
    control_port = _free_port()
    debug_port = _free_port()
    while debug_port == control_port:
        debug_port = _free_port()
    return control_port, debug_port


@pytest.fixture(scope='session')
def agent_runner_e2e_config_path(agent_runner_e2e_tmpdir, agent_runner_e2e_port, agent_runner_runtime_ports):
    """Create a plugin-enabled config and deterministic AgentRunner fixture."""
    config_path = create_minimal_config(agent_runner_e2e_tmpdir, port=agent_runner_e2e_port)
    create_test_directories(agent_runner_e2e_tmpdir)

    import yaml

    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)
    config['api']['global_api_key'] = 'e2e-agent-runner-key'
    runtime_control_port, _runtime_debug_port = agent_runner_runtime_ports
    config['plugin']['enable'] = True
    config['plugin']['runtime_ws_url'] = f'ws://127.0.0.1:{runtime_control_port}/control/ws'
    config['plugin']['enable_marketplace'] = False
    config['box']['enabled'] = False
    config['system']['jwt']['secret'] = 'e2e-agent-runner-secret-key'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    _write_qa_agent_runner_plugin(agent_runner_e2e_tmpdir / 'data' / 'plugins' / QA_PLUGIN_DIRNAME)
    return config_path


@pytest.fixture(scope='session')
def agent_runner_runtime_process(agent_runner_e2e_tmpdir, agent_runner_runtime_ports):
    """Start the real SDK plugin runtime over WebSocket."""
    control_port, debug_port = agent_runner_runtime_ports
    stdout_path = agent_runner_e2e_tmpdir / 'plugin-runtime.stdout.log'
    stderr_path = agent_runner_e2e_tmpdir / 'plugin-runtime.stderr.log'
    stdout_file = open(stdout_path, 'wb')
    stderr_file = open(stderr_path, 'wb')
    proc = subprocess.Popen(
        [
            str(find_project_root() / '.venv' / 'bin' / 'python'),
            '-m',
            'langbot_plugin.cli.__init__',
            'rt',
            '--ws-control-port',
            str(control_port),
            '--ws-debug-port',
            str(debug_port),
        ],
        cwd=agent_runner_e2e_tmpdir,
        stdout=stdout_file,
        stderr=stderr_file,
        start_new_session=True,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    stdout_file.close()
    stderr_file.close()


@pytest.fixture(scope='session')
def agent_runner_langbot_process(
    agent_runner_e2e_config_path,
    agent_runner_e2e_port,
    agent_runner_e2e_tmpdir,
    agent_runner_runtime_process,
):
    """Start real LangBot with plugin runtime enabled."""
    project_root = find_project_root()
    proc = LangBotProcess(
        project_root=project_root,
        work_dir=agent_runner_e2e_tmpdir,
        port=agent_runner_e2e_port,
        timeout=180,
        debug=True,
        cli_args=['--standalone-runtime'],
    )

    success = proc.start()
    if not success:
        stdout, stderr = proc.get_logs()
        pytest.fail(f'LangBot failed to start with AgentRunner plugin runtime:\nstdout: {stdout}\nstderr: {stderr}')

    yield proc

    proc.stop()


@pytest.fixture
def agent_runner_client(agent_runner_e2e_port, agent_runner_langbot_process):
    """HTTP client for the AgentRunner E2E backend."""
    with httpx.Client(
        base_url=f'http://127.0.0.1:{agent_runner_e2e_port}',
        timeout=90.0,
        trust_env=False,
    ) as client:
        yield client


def _init_and_auth(client: httpx.Client) -> str:
    """Initialize the test admin user and return a bearer token."""
    init_resp = client.post('/api/v1/user/init', json={'user': 'admin', 'password': 'admin'})
    assert init_resp.status_code == 200
    assert init_resp.json()['code'] in [0, 1]

    auth_resp = client.post('/api/v1/user/auth', json={'user': 'admin', 'password': 'admin'})
    assert auth_resp.status_code == 200
    payload = auth_resp.json()
    assert payload['code'] == 0
    return payload['data']['token']


def test_plugin_runtime_discovers_agent_runner(agent_runner_client, agent_runner_langbot_process):
    """Pipeline metadata should include the real runtime-discovered QA runner."""
    token = _init_and_auth(agent_runner_client)
    start = time.time()
    while time.time() - start < 60:
        response = agent_runner_client.get(
            '/api/v1/pipelines/_/metadata',
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['code'] == 0
        metadata_groups = data['data']['configs']
        ai_metadata = next(group for group in metadata_groups if group.get('name') == 'ai')

        runner_stage = next(stage for stage in ai_metadata['stages'] if stage['name'] == 'runner')
        runner_select = next(item for item in runner_stage['config'] if item['name'] == 'id')
        option_names = {option['name'] for option in runner_select['options']}
        if QA_RUNNER_ID in option_names:
            return
        time.sleep(2)

    assert QA_RUNNER_ID in option_names

def test_host_orchestrator_runs_agent_runner_and_records_ledger(
    agent_runner_e2e_config_path,
    agent_runner_e2e_tmpdir,
    agent_runner_runtime_process,
):
    """The Host orchestrator should run the pluginized runner and persist run side effects."""
    import asyncio
    import os

    from langbot.pkg.agent.runner.host_models import (
        AgentBinding,
        AgentEventEnvelope,
        BindingScope,
        DeliveryPolicy,
        StatePolicy,
    )
    from langbot.pkg.core import boot
    from langbot.pkg.utils import platform as platform_utils
    from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
    from langbot_plugin.api.entities.builtin.agent_runner.event import ActorContext, SubjectContext
    from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput

    async def _run_probe():
        previous_cwd = Path.cwd()
        previous_standalone_runtime = platform_utils.standalone_runtime
        os.chdir(agent_runner_e2e_tmpdir)
        platform_utils.standalone_runtime = True
        ap = None
        try:
            ap = await boot.make_app(asyncio.get_running_loop())
            for _ in range(60):
                handler = getattr(ap.plugin_connector, 'handler', None)
                if handler is not None:
                    await handler.ping()
                    break
                await asyncio.sleep(1)
            else:
                raise AssertionError('Plugin runtime did not connect')

            for _ in range(60):
                runners = await ap.agent_runner_registry.list_runners(use_cache=False)
                if any(runner.id == QA_RUNNER_ID for runner in runners):
                    break
                await asyncio.sleep(1)
            else:
                raise AssertionError(f'{QA_RUNNER_ID} was not discovered')

            event = AgentEventEnvelope(
                event_id='e2e-orchestrator-event-001',
                event_type='message.received',
                source='api',
                conversation_id='e2e-conversation',
                thread_id='e2e-thread',
                actor=ActorContext(actor_type='user', actor_id='user-001', actor_name='E2E User'),
                subject=SubjectContext(subject_type='chat', subject_id='chat-001'),
                input=AgentInput(text='hello from orchestrator e2e'),
                delivery=DeliveryContext(surface='e2e'),
            )
            binding = AgentBinding(
                binding_id='e2e-binding',
                scope=BindingScope(scope_type='global'),
                runner_id=QA_RUNNER_ID,
                state_policy=StatePolicy(enable_state=True, state_scopes=['conversation']),
                delivery_policy=DeliveryPolicy(enable_streaming=False, enable_reply=True),
            )
            return [message async for message in ap.agent_run_orchestrator.run(event, binding)]
        finally:
            if ap is not None:
                ap.dispose()
            platform_utils.standalone_runtime = previous_standalone_runtime
            os.chdir(previous_cwd)

    messages = asyncio.run(_run_probe())

    assert len(messages) == 1
    assert messages[0].role == 'assistant'
    assert messages[0].content == 'e2e echo: hello from orchestrator e2e'

    db_path = agent_runner_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            "SELECT status, runner_id FROM agent_run WHERE event_id = 'e2e-orchestrator-event-001'"
        ).fetchone()
        assert run_row == ('completed', QA_RUNNER_ID)

        event_types = {
            row[0]
            for row in conn.execute(
                "SELECT type FROM agent_run_event WHERE run_id = (SELECT run_id FROM agent_run WHERE event_id = 'e2e-orchestrator-event-001')"
            ).fetchall()
        }
        assert {'state.updated', 'message.completed', 'run.completed'}.issubset(event_types)

        state_row = conn.execute(
            "SELECT value_json FROM agent_runner_state WHERE state_key = 'e2e.echo_count'"
        ).fetchone()
        assert state_row is not None
        assert '"count": 1' in state_row[0]
    finally:
        conn.close()


def test_pluginized_agent_runner_executes_through_runtime(agent_runner_client, agent_runner_langbot_process):
    """The Host debug surface should invoke the QA runner through the real Plugin Runtime."""
    token = _init_and_auth(agent_runner_client)
    start = time.time()
    while time.time() - start < 60:
        metadata_response = agent_runner_client.get(
            '/api/v1/pipelines/_/metadata',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert metadata_response.status_code == 200
        metadata = metadata_response.json()['data']['configs']
        ai_metadata = next(group for group in metadata if group.get('name') == 'ai')
        runner_stage = next(stage for stage in ai_metadata['stages'] if stage['name'] == 'runner')
        runner_select = next(item for item in runner_stage['config'] if item['name'] == 'id')
        if QA_RUNNER_ID in {option['name'] for option in runner_select['options']}:
            break
        time.sleep(2)
    else:
        pytest.fail(f'{QA_RUNNER_ID} was not discovered before run_agent')

    response = agent_runner_client.post(
        '/api/v1/system/debug/plugin/action',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'action': 'run_agent',
            'timeout': 60,
            'data': {
                'plugin_author': 'e2e',
                'plugin_name': 'agent-runner-qa',
                'runner_name': 'default',
                'context': {
                    'run_id': 'e2e-run-001',
                    'trigger': {'type': 'message.received'},
                    'event': {
                        'event_id': 'e2e-event-001',
                        'event_type': 'message.received',
                        'source': 'api',
                    },
                    'input': {'text': 'hello from real e2e'},
                    'delivery': {'surface': 'e2e'},
                    'resources': {},
                    'runtime': {},
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['code'] == 0
    result = payload['data']
    assert result['type'] == 'message.completed', result
    assert result['data']['message']['role'] == 'assistant'
    assert result['data']['message']['content'] == 'e2e echo: hello from real e2e'
