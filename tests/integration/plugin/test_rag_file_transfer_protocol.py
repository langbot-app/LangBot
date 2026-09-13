"""Real Core/SDK protocol regression tests; no subprocesses or external services.

Run against the intended local SDK (``uv run --no-sync`` after local install).
The in-memory transport carries JSON strings through Handler.run on both sides;
send_file, envelope validation, base64 decoding and transfer storage are real.
Only Core's database/object-storage services, parser dispatch/provider and host
sandbox prerequisite probing are doubles. Worker launch/registration is
represented by its already-registered state.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot_plugin.entities.io.actions.enums import CommonAction, LangBotToRuntimeAction, PluginToRuntimeAction
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding, PluginWorkerPolicy, RuntimeIdentity
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.entities.io.errors import ActionCallError, ConnectionClosedError
from langbot_plugin.runtime.io.handler import FILE_CHUNK_LENGTH, Handler
from langbot_plugin.runtime.io.handlers.control import ControlConnectionHandler
from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler
from langbot_plugin.runtime.plugin.mgr import PluginManager
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV


pytestmark = pytest.mark.asyncio
PAYLOAD = bytes(range(256)) * 161 + b'\x00original RAG file\xff'
BINDING = InstallationBinding(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=7,
    installation_uuid='00000000-0000-4000-8000-000000000001',
    runtime_revision=3,
    artifact_digest='a' * 64,
)
LEGACY = ActionContext(**BINDING.model_dump(exclude={'runtime_revision', 'artifact_digest'}))


class QueueConnection(Connection):
    """Only the byte transport is replaced, not the request/response machinery."""

    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.peer = None

    async def send(self, message: str) -> None:
        assert isinstance(message, str)
        self.sent.append(json.loads(message))
        await self.peer.incoming.put(message)

    async def receive(self) -> str:
        message = await self.incoming.get()
        if message is None:
            raise ConnectionClosedError('test transport closed')
        return message

    async def close(self) -> None:
        await self.incoming.put(None)
        await self.peer.incoming.put(None)


def connection_pair():
    left, right = QueueConnection(), QueueConnection()
    left.peer, right.peer = right, left
    return left, right


@asynccontextmanager
async def protocol_stack(tmp_path, monkeypatch, profile='oss_dev', binding=LEGACY):
    monkeypatch.chdir(tmp_path)
    stored = tmp_path / 'original.bin'
    stored.write_bytes(PAYLOAD)
    storage_calls = []

    async def get_file_stream(execution_context, storage_path):
        storage_calls.append((execution_context, storage_path))
        assert execution_context.workspace_uuid == BINDING.workspace_uuid
        assert storage_path == 'knowledge/original.bin'
        return stored.read_bytes()

    async def get_execution_binding(workspace_uuid, expected_generation):
        assert workspace_uuid == BINDING.workspace_uuid
        assert expected_generation == BINDING.placement_generation
        return BINDING

    setting = SimpleNamespace(
        plugin_author='tester',
        plugin_name='engine',
        installation_uuid=BINDING.installation_uuid,
        runtime_revision=BINDING.runtime_revision,
        artifact_digest=BINDING.artifact_digest,
    )
    app = SimpleNamespace(
        deployment=SimpleNamespace(mode='oss' if profile == 'oss_dev' else 'cloud'),
        logger=logging.getLogger(__name__),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=SimpleNamespace(first=lambda: setting))),
        workspace_service=SimpleNamespace(get_execution_binding=get_execution_binding),
        rag_runtime_service=SimpleNamespace(get_file_stream=get_file_stream),
    )
    core_conn, control_conn = connection_pair()
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(tmp_path / 'core-transfer'))
    core = RuntimeConnectionHandler(core_conn, AsyncMock(return_value=False), app)
    core.register_installation_binding(BINDING, plugin_author='tester', plugin_name='engine')
    runtime = RuntimeContext()
    runtime.plugin_mgr = PluginManager(runtime)
    # No worker is launched: omit only host nsjail/cgroup prerequisite probing.
    monkeypatch.setattr(runtime.plugin_mgr.worker_launcher, 'configure', lambda policy, profile: None)
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(tmp_path / 'runtime-transfer'))
    control = ControlConnectionHandler(control_conn, runtime)
    runtime.activate_control_handler(control)
    bridge_conn, plugin_conn = connection_pair()
    bridge = PluginConnectionHandler(bridge_conn, runtime, file_storage_dir=str(tmp_path / 'bridge-transfer'))
    plugin = Handler(plugin_conn, file_storage_dir=str(tmp_path / 'plugin-transfer'))
    # Trusted state left by registration, not plugin-supplied action data.
    bridge.bind_action_context(binding)
    runtime.plugin_mgr.plugin_handlers.append(bridge)
    runtime.plugin_mgr.plugins.append(SimpleNamespace(_runtime_plugin_handler=bridge))
    handlers = [core, control, bridge, plugin]
    tasks = [asyncio.create_task(handler.run()) for handler in handlers]
    try:
        await asyncio.wait_for(
            core.set_runtime_config(
                runtime_identity=RuntimeIdentity(instance_uuid='instance-a', runtime_id='test-runtime'),
                worker_policy=PluginWorkerPolicy(
                    max_cpus=1,
                    max_memory_mb=128,
                    max_pids=32,
                    max_open_files=64,
                    max_file_size_mb=8,
                    require_hard_limits=False,
                ),
                runtime_profile=profile,
                cloud_service_url=None,
            ),
            5,
        )
        if isinstance(binding, InstallationBinding):
            runtime.activate_installation_binding(binding)
        else:
            runtime.bind_workspace(binding)
        yield SimpleNamespace(
            core=core,
            control=control,
            runtime=runtime,
            bridge=bridge,
            plugin=plugin,
            core_conn=core_conn,
            control_conn=control_conn,
            bridge_conn=bridge_conn,
            plugin_conn=plugin_conn,
            app=app,
            storage_calls=storage_calls,
        )
    finally:
        for handler in handlers:
            await handler.close()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)


def assert_chunks(connection, binding, payload=PAYLOAD):
    chunks = [message for message in connection.sent if message.get('action') == CommonAction.FILE_CHUNK.value]
    expected = (len(payload) + FILE_CHUNK_LENGTH - 1) // FILE_CHUNK_LENGTH
    assert expected > 1
    assert len(chunks) == expected
    assert [chunk['data']['chunk_index'] for chunk in chunks] == list(range(expected))
    assert {chunk['data']['chunk_amount'] for chunk in chunks} == {expected}
    assert all(chunk['context'] == binding.model_dump() for chunk in chunks)
    assert len({chunk['data']['file_key'] for chunk in chunks}) == 1
    return chunks[0]['data']['file_key']


@pytest.mark.parametrize(
    'profile,binding',
    [('oss_dev', LEGACY), ('oss_dev', BINDING), ('shared', BINDING)],
    ids=['legacy-oss', 'managed-oss', 'managed-shared'],
)
async def test_knowledge_file_roundtrip_reaches_plugin_original_bytes(tmp_path, monkeypatch, profile, binding):
    async with protocol_stack(tmp_path, monkeypatch, profile, binding) as stack:
        # Legacy plugin API sends no authority; Runtime supplies its trusted binding.
        result = await asyncio.wait_for(
            stack.plugin.call_action(
                PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM,
                {'storage_path': 'knowledge/original.bin'},
            ),
            5,
        )
        assert await stack.plugin.read_local_file(result['file_key']) == PAYLOAD
        assert len(stack.storage_calls) == 1
        core_key = assert_chunks(stack.core_conn, binding)
        plugin_key = assert_chunks(stack.bridge_conn, binding)
        assert result['file_key'] == plugin_key != core_key
        assert not (Path(stack.control.file_storage_dir) / core_key).exists()
        assert not stack.control._owned_transfer_files
        callbacks = [
            message
            for message in stack.control_conn.sent
            if message.get('action') == PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM.value
        ]
        assert len(callbacks) == 1
        assert callbacks[0]['context'] == binding.model_dump()
        assert callbacks[0]['data'] == {'storage_path': 'knowledge/original.bin'}


async def test_shared_control_rejects_legacy_chunks_before_storage(tmp_path, monkeypatch):
    async with protocol_stack(tmp_path, monkeypatch, 'shared', BINDING) as stack:
        with stack.core.installation_scope(LEGACY):
            with pytest.raises(ActionCallError, match='InstallationBinding|Legacy FILE_CHUNK'):
                await asyncio.wait_for(stack.core.send_file(PAYLOAD, ''), 5)
        assert not list(Path(stack.control.file_storage_dir).iterdir())
        assert not stack.control._owned_transfer_files


async def test_candidate_artifact_pretransfer_does_not_require_active_installation(tmp_path, monkeypatch):
    async with protocol_stack(tmp_path, monkeypatch, 'shared', BINDING) as stack:
        candidate = BINDING.model_copy(
            update={'installation_uuid': 'candidate-installation', 'runtime_revision': 1, 'artifact_digest': 'c' * 64}
        )
        assert not stack.runtime.is_current_installation_binding(candidate)
        with stack.core.installation_scope(candidate):
            key = await asyncio.wait_for(stack.core.send_file(PAYLOAD, 'lbp'), 5)
        assert_chunks(stack.core_conn, candidate)
        assert await stack.control.read_local_file(key) == PAYLOAD
        assert not stack.runtime.is_current_installation_binding(candidate)


async def test_nested_parser_target_owns_file_and_action_envelopes(tmp_path, monkeypatch):
    async with protocol_stack(tmp_path, monkeypatch, 'shared', BINDING) as stack:
        target = BINDING.model_copy(
            update={
                'installation_uuid': 'parser-installation',
                'runtime_revision': 2,
                'artifact_digest': 'b' * 64,
            }
        )
        stack.runtime.activate_installation_binding(target)
        parser_calls = []
        restored = []

        async def parse_document(author, name, context_data, file_bytes):
            parser_calls.append((stack.control.current_action_context, author, name, context_data, file_bytes))
            return {'documents': [{'text': 'parsed'}]}

        stack.runtime.plugin_mgr.parse_document = parse_document

        class ParserConnector:
            async def require_workspace_context(self, context):
                assert context.workspace_uuid == BINDING.workspace_uuid

            async def call_parser(self, plugin_name, context_data, file_bytes):
                assert plugin_name == 'tester/parser'
                assert stack.core.current_action_context == BINDING
                with stack.core.installation_scope(target):
                    result = await stack.core.parse_document('tester', 'parser', context_data, file_bytes)
                restored.append(stack.core.resolve_outbound_action_context(None))
                return result

        stack.app.plugin_connector = ParserConnector()
        result = await asyncio.wait_for(
            stack.plugin.call_action(
                PluginToRuntimeAction.INVOKE_PARSER,
                {
                    'plugin_author': 'tester',
                    'plugin_name': 'parser',
                    'storage_path': 'knowledge/original.bin',
                    'filename': 'original.bin',
                },
            ),
            5,
        )
        assert result == {'documents': [{'text': 'parsed'}]}
        key = assert_chunks(stack.core_conn, target)
        parse_requests = [
            message
            for message in stack.core_conn.sent
            if message.get('action') == LangBotToRuntimeAction.PARSE_DOCUMENT.value
        ]
        assert len(parse_requests) == 1
        assert parse_requests[0]['context'] == target.model_dump()
        assert parse_requests[0]['data']['context']['file_key'] == key
        assert parser_calls == [
            (
                target,
                'tester',
                'parser',
                {
                    'mime_type': 'application/octet-stream',
                    'filename': 'original.bin',
                    'metadata': {},
                },
                PAYLOAD,
            )
        ]
        assert restored == [BINDING]
        assert stack.core.current_action_context is None
        assert stack.core.resolve_outbound_action_context(None) is None
        assert not (Path(stack.control.file_storage_dir) / key).exists()
