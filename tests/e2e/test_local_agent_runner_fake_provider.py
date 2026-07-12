"""E2E coverage for the official Local Agent runner with fake Host resources.

These tests start the real LangBot application and the real SDK Plugin Runtime,
load the sibling ``langbot-local-agent`` plugin, and verify Local Agent paths
that must cross Host run-scoped APIs without calling any external provider.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.e2e.utils.process_manager import find_project_root

pytestmark = pytest.mark.e2e


LOCAL_AGENT_RUNNER_ID = 'plugin:langbot-team/LocalAgent/default'
FAKE_PROVIDER_UUID = 'e2e-fake-provider'
FAKE_MODEL_UUID = 'e2e-fake-local-agent-model'
LOCAL_AGENT_PLUGIN_DIRNAME = 'langbot__local-agent'
E2E_TOOL_NAME = 'e2e_lookup'
E2E_KB_UUID = 'e2e-kb-local-agent'


def _free_port() -> int:
    """Reserve a currently-free localhost TCP port for this E2E process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _local_agent_repo() -> Path:
    """Return the sibling local-agent repository used by this workspace E2E."""
    project_root = find_project_root()
    return project_root.parent / 'langbot-local-agent'


def _copy_local_agent_plugin(tmpdir: Path) -> None:
    """Copy the sibling Local Agent plugin into the temporary LangBot data dir."""
    local_agent_src = _local_agent_repo()
    if not (local_agent_src / 'manifest.yaml').exists():
        pytest.skip(f'local-agent repository not found at {local_agent_src}')

    plugin_dst = tmpdir / 'data' / 'plugins' / LOCAL_AGENT_PLUGIN_DIRNAME
    ignore = shutil.ignore_patterns(
        '.git',
        '.venv',
        '__pycache__',
        '.pytest_cache',
        '.ruff_cache',
        'build',
        'dist',
    )
    shutil.copytree(local_agent_src, plugin_dst, ignore=ignore)


def _content_text(content: Any) -> str:
    """Flatten provider message content into text for assertions."""
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = item.get('text') if isinstance(item, dict) else getattr(item, 'text', None)
            if text:
                parts.append(str(text))
        return ''.join(parts)
    return str(content)


def _message_text(message: Any) -> str:
    """Flatten a provider message into text for assertions."""
    return _content_text(getattr(message, 'content', None))


def _invoke_payload_texts(fake_requester: Any) -> list[list[str]]:
    """Return model-facing text for every fake LLM invocation."""
    payloads: list[list[str]] = []
    for payload in fake_requester._invoke_payloads:
        payloads.append([_message_text(message) for message in payload['messages']])
    return payloads


def _event(
    *,
    event_id: str,
    conversation_id: str,
    text: str,
    thread_id: str = 'e2e-local-agent-thread',
):
    """Build an AgentRunner event envelope for Local Agent E2E probes."""
    from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
    from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
    from langbot_plugin.api.entities.builtin.agent_runner.event import ActorContext, SubjectContext
    from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput

    return AgentEventEnvelope(
        event_id=event_id,
        event_type='message.received',
        source='api',
        conversation_id=conversation_id,
        thread_id=thread_id,
        actor=ActorContext(actor_type='user', actor_id='user-001', actor_name='E2E User'),
        subject=SubjectContext(subject_type='chat', subject_id='chat-001'),
        input=AgentInput(text=text),
        delivery=DeliveryContext(surface='e2e', supports_streaming=False),
    )


def _binding(
    *,
    binding_id: str = 'e2e-local-agent-binding',
    runner_config: dict[str, Any] | None = None,
    allowed_tool_names: list[str] | None = None,
    allowed_kb_uuids: list[str] | None = None,
):
    """Build a Local Agent binding with fake model access."""
    from langbot.pkg.agent.runner.host_models import (
        AgentBinding,
        BindingScope,
        DeliveryPolicy,
        ResourcePolicy,
        StatePolicy,
    )

    config = {
        'model': {'primary': FAKE_MODEL_UUID, 'fallbacks': []},
        'timeout': 60,
        'prompt': [{'role': 'system', 'content': 'You are a concise test assistant.'}],
        'knowledge-bases': [],
        'context-window-tokens': 8192,
        'context-reserve-tokens': 1024,
        'context-keep-recent-tokens': 1000,
        'context-summary-tokens': 500,
    }
    if runner_config:
        config.update(runner_config)

    return AgentBinding(
        binding_id=binding_id,
        scope=BindingScope(scope_type='global'),
        runner_id=LOCAL_AGENT_RUNNER_ID,
        runner_config=config,
        resource_policy=ResourcePolicy(
            allowed_model_uuids=[FAKE_MODEL_UUID],
            allowed_tool_names=allowed_tool_names,
            allowed_kb_uuids=allowed_kb_uuids,
        ),
        state_policy=StatePolicy(enable_state=True, state_scopes=['conversation']),
        delivery_policy=DeliveryPolicy(enable_streaming=False, enable_reply=True),
    )


class _FakeToolManager:
    """Deterministic tool manager used behind the real Host CALL_TOOL action."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def get_tool_schema(self, tool_name: str):
        if tool_name != E2E_TOOL_NAME:
            return None, None
        return (
            'Lookup a deterministic E2E value.',
            {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'},
                },
                'required': ['query'],
            },
        )

    async def get_tool_detail(self, tool_name: str):
        description, parameters = await self.get_tool_schema(tool_name)
        if parameters is None:
            return None
        return {'name': tool_name, 'description': description, 'parameters': parameters}

    async def execute_func_call(self, name: str, parameters: dict[str, Any], query: Any = None):
        del query
        self.calls.append({'name': name, 'parameters': dict(parameters)})
        return {
            'value': f"tool-result:{parameters.get('query')}",
            'source': 'fake-tool-manager',
        }


class _FakeKnowledgeBase:
    """Minimal KB object used behind the real Host RETRIEVE_KNOWLEDGE action."""

    def __init__(self):
        self.knowledge_base_entity = SimpleNamespace(kb_type='fake')
        self.retrieve_calls: list[dict[str, Any]] = []

    def get_uuid(self) -> str:
        return E2E_KB_UUID

    def get_name(self) -> str:
        return 'E2E Fake KB'

    async def retrieve(self, query_text: str, settings: dict[str, Any]):
        self.retrieve_calls.append({'query_text': query_text, 'settings': settings})
        return [
            SimpleNamespace(
                content='RAG_SENTINEL Local Agent retrieved this deterministic chunk.',
                metadata={'source': 'fake-kb'},
                id='fake-kb-chunk-1',
                score=0.99,
                model_dump=lambda mode='json': {
                    'content': 'RAG_SENTINEL Local Agent retrieved this deterministic chunk.',
                    'metadata': {'source': 'fake-kb'},
                    'id': 'fake-kb-chunk-1',
                    'score': 0.99,
                },
            )
        ]


class _FakeRagManager:
    """Deterministic RAG manager used by resource builder and retrieval action."""

    def __init__(self, kb: _FakeKnowledgeBase):
        self.kb = kb
        self.knowledge_bases = {E2E_KB_UUID: kb}

    async def get_knowledge_base_by_uuid(self, kb_uuid: str):
        if kb_uuid == E2E_KB_UUID:
            return self.kb
        return None


@pytest.fixture(scope='session')
def local_agent_e2e_tmpdir():
    """Create temporary directory for Local Agent E2E testing."""
    tmpdir = Path(tempfile.mkdtemp(prefix='langbot_local_agent_e2e_'))
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope='session')
def local_agent_e2e_port() -> int:
    """HTTP port for the real LangBot app used by this E2E."""
    return _free_port()


@pytest.fixture(scope='session')
def local_agent_runtime_ports() -> tuple[int, int]:
    """Control/debug ports for the standalone plugin runtime."""
    control_port = _free_port()
    debug_port = _free_port()
    while debug_port == control_port:
        debug_port = _free_port()
    return control_port, debug_port


@pytest.fixture(scope='session')
def local_agent_e2e_config_path(local_agent_e2e_tmpdir, local_agent_e2e_port, local_agent_runtime_ports):
    """Create a plugin-enabled config and install the Local Agent plugin fixture."""
    config_path = create_minimal_config(local_agent_e2e_tmpdir, port=local_agent_e2e_port)
    create_test_directories(local_agent_e2e_tmpdir)

    import yaml

    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)
    runtime_control_port, _runtime_debug_port = local_agent_runtime_ports
    config['api']['global_api_key'] = 'e2e-local-agent-key'
    config['plugin']['enable'] = True
    config['plugin']['runtime_ws_url'] = f'ws://127.0.0.1:{runtime_control_port}/control/ws'
    config['plugin']['enable_marketplace'] = False
    config['box']['enabled'] = False
    config['system']['jwt']['secret'] = 'e2e-local-agent-secret-key'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    _copy_local_agent_plugin(local_agent_e2e_tmpdir)
    return config_path


@pytest.fixture(scope='session')
def local_agent_runtime_process(local_agent_e2e_tmpdir, local_agent_runtime_ports, local_agent_e2e_config_path):
    """Start the real SDK plugin runtime over WebSocket."""
    del local_agent_e2e_config_path
    control_port, debug_port = local_agent_runtime_ports
    stdout_path = local_agent_e2e_tmpdir / 'plugin-runtime.stdout.log'
    stderr_path = local_agent_e2e_tmpdir / 'plugin-runtime.stderr.log'
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
        cwd=local_agent_e2e_tmpdir,
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


def _inject_fake_llm_model(ap) -> Any:
    """Register a runtime-only fake model that supports count_tokens/invoke."""
    from langbot.pkg.entity.persistence import model as persistence_model
    from langbot.pkg.provider.modelmgr import requester, token
    from tests.unit_tests.provider.conftest import FakeProviderAPIRequester

    provider_entity = persistence_model.ModelProvider(
        uuid=FAKE_PROVIDER_UUID,
        name='E2E Fake Provider',
        requester='fake-requester',
        base_url='https://fake.invalid',
        api_keys=['fake-key'],
    )
    fake_requester = FakeProviderAPIRequester(ap, {'base_url': provider_entity.base_url})
    runtime_provider = requester.RuntimeProvider(
        provider_entity=provider_entity,
        token_mgr=token.TokenManager(name=provider_entity.uuid, tokens=provider_entity.api_keys),
        requester=fake_requester,
    )
    runtime_model = requester.RuntimeLLMModel(
        model_entity=persistence_model.LLMModel(
            uuid=FAKE_MODEL_UUID,
            name=FAKE_MODEL_UUID,
            provider_uuid=provider_entity.uuid,
            abilities=['func_call'],
            context_length=8192,
            extra_args={},
        ),
        provider=runtime_provider,
    )
    ap.model_mgr.provider_dict[provider_entity.uuid] = runtime_provider
    ap.model_mgr.llm_models.append(runtime_model)
    return fake_requester


def _scripted_tool_call(
    tool_name: str = E2E_TOOL_NAME,
    *,
    call_id: str = 'call-e2e-lookup',
    query: str = 'alpha',
):
    """Build an assistant message requesting a deterministic tool call."""
    from langbot_plugin.api.entities.builtin.provider import message as provider_message

    return provider_message.Message(
        role='assistant',
        content='',
        tool_calls=[
            provider_message.ToolCall(
                id=call_id,
                type='function',
                function=provider_message.FunctionCall(
                    name=tool_name,
                    arguments=json.dumps({'query': query}, ensure_ascii=False),
                ),
            )
        ],
    )


async def _boot_local_agent_app(tmpdir: Path):
    """Boot LangBot and wait until the Local Agent runner is discoverable."""
    from langbot.pkg.core import boot

    ap = await boot.make_app(asyncio.get_running_loop())
    for _ in range(60):
        handler = getattr(ap.plugin_connector, 'handler', None)
        if handler is not None:
            await handler.ping()
            break
        await asyncio.sleep(1)
    else:
        raise AssertionError(f'Plugin runtime did not connect; tmpdir={tmpdir}')

    for _ in range(60):
        runners = await ap.agent_runner_registry.list_runners(use_cache=False)
        if any(runner.id == LOCAL_AGENT_RUNNER_ID for runner in runners):
            break
        await asyncio.sleep(1)
    else:
        raise AssertionError(f'{LOCAL_AGENT_RUNNER_ID} was not discovered')

    return ap


def _run_local_agent_probe(tmpdir: Path, probe):
    """Run one Local Agent probe inside the temporary LangBot app."""
    from langbot.pkg.utils import platform as platform_utils

    async def _run():
        previous_cwd = Path.cwd()
        previous_standalone_runtime = platform_utils.standalone_runtime
        os.chdir(tmpdir)
        platform_utils.standalone_runtime = True
        ap = None
        try:
            ap = await _boot_local_agent_app(tmpdir)
            return await probe(ap)
        finally:
            if ap is not None:
                ap.dispose()
            platform_utils.standalone_runtime = previous_standalone_runtime
            os.chdir(previous_cwd)

    return asyncio.run(_run())


def test_local_agent_runner_uses_host_fake_provider_and_persists_ledger(
    local_agent_e2e_tmpdir,
    local_agent_e2e_config_path,
    local_agent_runtime_process,
):
    """Local Agent should execute through Host APIs with a token-free fake provider."""
    del local_agent_e2e_config_path, local_agent_runtime_process

    async def _run_probe(ap):
        fake_requester = _inject_fake_llm_model(ap)
        event = _event(
            event_id='e2e-local-agent-event-001',
            conversation_id='e2e-local-agent-conversation',
            text='Say pong through the fake provider.',
        )
        messages = [message async for message in ap.agent_run_orchestrator.run(event, _binding())]
        return messages, list(fake_requester._count_tokens_payloads)

    messages, token_payloads = _run_local_agent_probe(local_agent_e2e_tmpdir, _run_probe)

    assert len(messages) == 1
    assert messages[0].role == 'assistant'
    assert _content_text(messages[0].content) == 'Fake LLM response'
    assert token_payloads
    flattened_token_payloads = [item for payload in token_payloads for item in payload]
    assert any(item.get('role') == 'system' for item in flattened_token_payloads)
    assert any('Say pong through the fake provider.' in item.get('content', '') for item in flattened_token_payloads)

    db_path = local_agent_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            "SELECT run_id, status, runner_id, status_reason FROM agent_run WHERE event_id = ?",
            ('e2e-local-agent-event-001',),
        ).fetchone()
        assert run_row is not None
        run_id, status, runner_id, status_reason = run_row
        assert status == 'completed'
        assert runner_id == LOCAL_AGENT_RUNNER_ID
        assert status_reason == 'stop'

        event_rows = conn.execute(
            'SELECT sequence, type, data_json FROM agent_run_event WHERE run_id = ? ORDER BY sequence',
            (run_id,),
        ).fetchall()
        event_types = [row[1] for row in event_rows]
        assert event_types == ['message.completed', 'run.completed']
        assert 'Fake LLM response' in event_rows[0][2]

        transcript_rows = conn.execute(
            'SELECT role, content, run_id, runner_id FROM transcript WHERE conversation_id = ? ORDER BY seq',
            ('e2e-local-agent-conversation',),
        ).fetchall()
        assert [row[0] for row in transcript_rows] == ['user', 'assistant']
        assert transcript_rows[0][1] == 'Say pong through the fake provider.'
        assert transcript_rows[1][1] == 'Fake LLM response'
        assert transcript_rows[1][2] == run_id
        assert transcript_rows[1][3] == LOCAL_AGENT_RUNNER_ID
    finally:
        conn.close()


def test_local_agent_runner_executes_authorized_tool_loop_through_host_action(
    local_agent_e2e_tmpdir,
    local_agent_e2e_config_path,
    local_agent_runtime_process,
):
    """Local Agent should execute a model tool call through Host CALL_TOOL and finish."""
    del local_agent_e2e_config_path, local_agent_runtime_process

    async def _run_probe(ap):
        fake_requester = _inject_fake_llm_model(ap)
        fake_requester.queue_llm_responses(
            _scripted_tool_call(),
            'Tool loop final answer after tool-result:alpha',
        )
        tool_mgr = _FakeToolManager()
        ap.tool_mgr = tool_mgr

        event = _event(
            event_id='e2e-local-agent-tool-event-001',
            conversation_id='e2e-local-agent-tool-conversation',
            text='Use the e2e lookup tool before answering.',
        )
        binding = _binding(
            binding_id='e2e-local-agent-tool-binding',
            allowed_tool_names=[E2E_TOOL_NAME],
            runner_config={
                'max-tool-iterations': 2,
                'tool-execution-mode': 'serial',
            },
        )
        messages = [message async for message in ap.agent_run_orchestrator.run(event, binding)]
        return messages, tool_mgr.calls, _invoke_payload_texts(fake_requester)

    messages, tool_calls, invoke_payload_texts = _run_local_agent_probe(local_agent_e2e_tmpdir, _run_probe)

    assert len(messages) == 1
    assert _content_text(messages[0].content) == 'Tool loop final answer after tool-result:alpha'
    assert tool_calls == [{'name': E2E_TOOL_NAME, 'parameters': {'query': 'alpha'}}]
    assert any('tool-result:alpha' in text for text in invoke_payload_texts[-1])

    db_path = local_agent_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            "SELECT run_id, status, status_reason FROM agent_run WHERE event_id = ?",
            ('e2e-local-agent-tool-event-001',),
        ).fetchone()
        assert run_row is not None
        run_id, status, status_reason = run_row
        assert status == 'completed'
        assert status_reason == 'stop'

        event_rows = conn.execute(
            'SELECT type, data_json FROM agent_run_event WHERE run_id = ? ORDER BY sequence',
            (run_id,),
        ).fetchall()
        event_types = [row[0] for row in event_rows]
        assert event_types == [
            'tool.call.started',
            'tool.call.completed',
            'message.completed',
            'run.completed',
        ]
        assert E2E_TOOL_NAME in event_rows[0][1]
        assert 'tool-result:alpha' in event_rows[1][1]
    finally:
        conn.close()


def test_local_agent_runner_retrieves_authorized_rag_context_through_host_action(
    local_agent_e2e_tmpdir,
    local_agent_e2e_config_path,
    local_agent_runtime_process,
):
    """Local Agent should retrieve configured KB context through Host RETRIEVE_KNOWLEDGE."""
    del local_agent_e2e_config_path, local_agent_runtime_process

    async def _run_probe(ap):
        fake_requester = _inject_fake_llm_model(ap)
        fake_requester.queue_llm_responses('RAG final answer with RAG_SENTINEL')
        fake_kb = _FakeKnowledgeBase()
        ap.rag_mgr = _FakeRagManager(fake_kb)

        event = _event(
            event_id='e2e-local-agent-rag-event-001',
            conversation_id='e2e-local-agent-rag-conversation',
            text='Answer with the retrieved RAG sentinel.',
        )
        binding = _binding(
            binding_id='e2e-local-agent-rag-binding',
            allowed_kb_uuids=[E2E_KB_UUID],
            runner_config={
                'knowledge-bases': [E2E_KB_UUID],
                'retrieval-top-k': 1,
            },
        )
        messages = [message async for message in ap.agent_run_orchestrator.run(event, binding)]
        return messages, fake_kb.retrieve_calls, _invoke_payload_texts(fake_requester)

    messages, retrieve_calls, invoke_payload_texts = _run_local_agent_probe(local_agent_e2e_tmpdir, _run_probe)

    assert len(messages) == 1
    assert _content_text(messages[0].content) == 'RAG final answer with RAG_SENTINEL'
    assert retrieve_calls == [
        {
            'query_text': 'Answer with the retrieved RAG sentinel.',
            'settings': {'top_k': 1, 'filters': {}},
        }
    ]
    assert any(
        'RAG_SENTINEL Local Agent retrieved this deterministic chunk.' in text
        for payload_texts in invoke_payload_texts
        for text in payload_texts
    )

    db_path = local_agent_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            "SELECT run_id, status FROM agent_run WHERE event_id = ?",
            ('e2e-local-agent-rag-event-001',),
        ).fetchone()
        assert run_row is not None
        run_id, status = run_row
        assert status == 'completed'
        event_types = [
            row[0]
            for row in conn.execute(
                'SELECT type FROM agent_run_event WHERE run_id = ? ORDER BY sequence',
                (run_id,),
            )
        ]
        assert event_types == ['message.completed', 'run.completed']
    finally:
        conn.close()


def test_local_agent_runner_compacts_history_and_persists_checkpoint(
    local_agent_e2e_tmpdir,
    local_agent_e2e_config_path,
    local_agent_runtime_process,
):
    """Local Agent should compact old Host history and write conversation checkpoint state."""
    del local_agent_e2e_config_path, local_agent_runtime_process

    async def _run_probe(ap):
        from langbot.pkg.agent.runner.transcript_store import TranscriptStore

        fake_requester = _inject_fake_llm_model(ap)
        fake_requester.queue_llm_responses(
            'SUMMARY_SENTINEL compacted older history including HIST_SENTINEL',
            'Compaction final answer',
        )

        store = TranscriptStore(ap.persistence_mgr.get_db_engine())
        for index in range(12):
            await store.append_transcript(
                transcript_id=None,
                event_id=f'e2e-local-agent-history-{index}',
                conversation_id='e2e-local-agent-compaction-conversation',
                role='user' if index % 2 == 0 else 'assistant',
                content=(
                    f'HIST_SENTINEL-{index} '
                    'This is intentionally long deterministic history for compaction. ' * 10
                ),
                thread_id='e2e-local-agent-thread',
                item_type='message',
            )

        event = _event(
            event_id='e2e-local-agent-compaction-event-001',
            conversation_id='e2e-local-agent-compaction-conversation',
            text='Use compacted context and answer.',
        )
        binding = _binding(
            binding_id='e2e-local-agent-compaction-binding',
            runner_config={
                'context-window-tokens': 900,
                'context-reserve-tokens': 300,
                'context-keep-recent-tokens': 160,
                'context-summary-tokens': 240,
                'context-history-fetch-limit': 20,
            },
        )
        messages = [message async for message in ap.agent_run_orchestrator.run(event, binding)]
        return messages, _invoke_payload_texts(fake_requester), fake_requester._invoke_count

    messages, invoke_payload_texts, invoke_count = _run_local_agent_probe(local_agent_e2e_tmpdir, _run_probe)

    assert len(messages) == 1
    assert _content_text(messages[0].content) == 'Compaction final answer'
    assert invoke_count == 2
    assert any('HIST_SENTINEL' in text for text in invoke_payload_texts[0])
    assert any('SUMMARY_SENTINEL compacted older history' in text for text in invoke_payload_texts[-1])

    db_path = local_agent_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            "SELECT run_id, status FROM agent_run WHERE event_id = ?",
            ('e2e-local-agent-compaction-event-001',),
        ).fetchone()
        assert run_row is not None
        run_id, status = run_row
        assert status == 'completed'

        event_types = [
            row[0]
            for row in conn.execute(
                'SELECT type FROM agent_run_event WHERE run_id = ? ORDER BY sequence',
                (run_id,),
            )
        ]
        assert event_types == ['message.completed', 'run.completed']

        state_row = conn.execute(
            "SELECT value_json FROM agent_runner_state WHERE state_key = 'runner.compaction.checkpoint'"
        ).fetchone()
        assert state_row is not None
        checkpoint = json.loads(state_row[0])
        assert checkpoint['schema_version'] == 'langbot.local_agent.compaction_checkpoint.v1'
        assert 'SUMMARY_SENTINEL compacted older history' in checkpoint['summary']
        assert checkpoint['conversation_id'] == 'e2e-local-agent-compaction-conversation'
        assert checkpoint['covers_until']
        assert checkpoint['tokens_before'] > 600
    finally:
        conn.close()


def test_local_agent_runner_combines_rag_compaction_and_multi_turn_tool_loop(
    local_agent_e2e_tmpdir,
    local_agent_e2e_config_path,
    local_agent_runtime_process,
):
    """Local Agent should preserve RAG, compressed history, and multi-turn tool results together."""
    del local_agent_e2e_config_path, local_agent_runtime_process

    async def _run_probe(ap):
        from langbot.pkg.agent.runner.transcript_store import TranscriptStore

        fake_requester = _inject_fake_llm_model(ap)

        async def scripted_response(**kwargs):
            messages = kwargs['messages']
            text = '\n'.join(_message_text(message) for message in messages)
            if 'context summarization assistant' in text or '<conversation>' in text:
                return 'SUMMARY_COMBO compacted older history including HIST_COMBO_SENTINEL and RAG_TOOL_COMBO_GOAL'
            if 'tool-result:alpha' not in text:
                return _scripted_tool_call(call_id='call-combo-alpha', query='alpha')
            if 'tool-result:beta' not in text:
                return _scripted_tool_call(call_id='call-combo-beta', query='beta')
            assert 'RAG_SENTINEL Local Agent retrieved this deterministic chunk.' in text
            assert 'SUMMARY_COMBO compacted older history' in text
            assert 'tool-result:alpha' in text
            assert 'tool-result:beta' in text
            assert 'current combo request must survive' in text
            return 'COMBO_FINAL RAG_SENTINEL HIST_COMBO_SENTINEL tool-result:alpha tool-result:beta'

        fake_requester.queue_llm_responses(*(scripted_response for _ in range(20)))
        tool_mgr = _FakeToolManager()
        fake_kb = _FakeKnowledgeBase()
        ap.tool_mgr = tool_mgr
        ap.rag_mgr = _FakeRagManager(fake_kb)

        store = TranscriptStore(ap.persistence_mgr.get_db_engine())
        for index in range(16):
            await store.append_transcript(
                transcript_id=None,
                event_id=f'e2e-local-agent-combo-history-{index}',
                conversation_id='e2e-local-agent-combo-conversation',
                role='user' if index % 2 == 0 else 'assistant',
                content=(
                    f'HIST_COMBO_SENTINEL-{index} RAG_TOOL_COMBO_GOAL '
                    'This old message intentionally creates pressure for combo compaction. ' * 8
                ),
                thread_id='e2e-local-agent-thread',
                item_type='message',
            )

        event = _event(
            event_id='e2e-local-agent-combo-event-001',
            conversation_id='e2e-local-agent-combo-conversation',
            text='current combo request must survive; use RAG and tools before answering.',
        )
        binding = _binding(
            binding_id='e2e-local-agent-combo-binding',
            allowed_tool_names=[E2E_TOOL_NAME],
            allowed_kb_uuids=[E2E_KB_UUID],
            runner_config={
                'knowledge-bases': [E2E_KB_UUID],
                'retrieval-top-k': 1,
                'max-tool-iterations': 4,
                'tool-execution-mode': 'serial',
                'context-window-tokens': 950,
                'context-reserve-tokens': 300,
                'context-keep-recent-tokens': 140,
                'context-summary-tokens': 260,
                'context-history-fetch-limit': 25,
            },
        )
        messages = [message async for message in ap.agent_run_orchestrator.run(event, binding)]
        return (
            messages,
            tool_mgr.calls,
            fake_kb.retrieve_calls,
            _invoke_payload_texts(fake_requester),
            fake_requester._invoke_count,
        )

    messages, tool_calls, retrieve_calls, invoke_payload_texts, invoke_count = _run_local_agent_probe(
        local_agent_e2e_tmpdir,
        _run_probe,
    )

    assert len(messages) == 1
    assert _content_text(messages[0].content) == (
        'COMBO_FINAL RAG_SENTINEL HIST_COMBO_SENTINEL tool-result:alpha tool-result:beta'
    )
    assert tool_calls == [
        {'name': E2E_TOOL_NAME, 'parameters': {'query': 'alpha'}},
        {'name': E2E_TOOL_NAME, 'parameters': {'query': 'beta'}},
    ]
    assert retrieve_calls == [
        {
            'query_text': 'current combo request must survive; use RAG and tools before answering.',
            'settings': {'top_k': 1, 'filters': {}},
        }
    ]
    assert invoke_count >= 4
    assert any(
        'RAG_SENTINEL Local Agent retrieved this deterministic chunk.' in text
        for payload_texts in invoke_payload_texts
        for text in payload_texts
    )
    assert any('SUMMARY_COMBO compacted older history' in text for text in invoke_payload_texts[-1])
    assert any('tool-result:alpha' in text for text in invoke_payload_texts[-1])
    assert any('tool-result:beta' in text for text in invoke_payload_texts[-1])
    assert any('current combo request must survive' in text for text in invoke_payload_texts[-1])

    db_path = local_agent_e2e_tmpdir / 'data' / 'langbot.db'
    conn = sqlite3.connect(str(db_path))
    try:
        run_row = conn.execute(
            "SELECT run_id, status, status_reason FROM agent_run WHERE event_id = ?",
            ('e2e-local-agent-combo-event-001',),
        ).fetchone()
        assert run_row is not None
        run_id, status, status_reason = run_row
        assert status == 'completed'
        assert status_reason == 'stop'

        event_rows = conn.execute(
            'SELECT type, data_json FROM agent_run_event WHERE run_id = ? ORDER BY sequence',
            (run_id,),
        ).fetchall()
        event_types = [row[0] for row in event_rows]
        assert event_types == [
            'tool.call.started',
            'tool.call.completed',
            'tool.call.started',
            'tool.call.completed',
            'message.completed',
            'run.completed',
        ]
        assert 'tool-result:alpha' in event_rows[1][1]
        assert 'tool-result:beta' in event_rows[3][1]
        assert 'COMBO_FINAL' in event_rows[4][1]

        state_rows = conn.execute(
            "SELECT value_json FROM agent_runner_state WHERE state_key = 'runner.compaction.checkpoint'"
        ).fetchall()
        checkpoints = [json.loads(row[0]) for row in state_rows]
        checkpoint = next(
            (
                item
                for item in checkpoints
                if item.get('conversation_id') == 'e2e-local-agent-combo-conversation'
            ),
            None,
        )
        assert checkpoint is not None
        assert checkpoint['conversation_id'] == 'e2e-local-agent-combo-conversation'
        assert 'SUMMARY_COMBO compacted older history' in checkpoint['summary']
    finally:
        conn.close()
