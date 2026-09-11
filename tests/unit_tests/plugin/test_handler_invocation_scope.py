"""Exercise nested installation routing through real Core/SDK wire envelopes."""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.entities.io.actions.enums import CommonAction, LangBotToRuntimeAction, PluginToRuntimeAction
from langbot_plugin.entities.io.req import ActionRequest
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io import handler as sdk_handler

from langbot.pkg.plugin.connector import PluginRuntimeConnector
from tests.unit_tests.plugin.test_handler_tenancy import RecordingConnection, make_handler, workspace_context


class ReplyingConnection(RecordingConnection):
    """Replace only the transport, retaining serialization and response routing."""

    async def send(self, message: str) -> None:
        await super().send(message)
        request = json.loads(message)
        if 'action' in request:
            response = ActionResponse.success({'elements': []})
            response.seq_id = request['seq_id']
            await self.handler._route_response(response.seq_id, response.model_dump())

    @property
    def requests(self):
        return [request for message in self.sent if 'action' in (request := json.loads(message))]


@pytest.fixture
def bridge(monkeypatch):
    runtime_handler, app, binding_a = make_handler()
    connection = ReplyingConnection()
    connection.handler = runtime_handler
    runtime_handler.conn = connection
    monkeypatch.setattr(sdk_handler, 'FILE_CHUNK_LENGTH', 4)
    binding_b = binding_a.model_copy(
        update={
            'installation_uuid': '00000000-0000-4000-8000-000000000002',
            'runtime_revision': 2,
            'artifact_digest': 'b' * 64,
        }
    )
    return runtime_handler, app, connection, binding_a, binding_b


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['managed', 'legacy'])
async def test_nested_invoke_parser_uses_target_for_every_chunk_and_parse(bridge, mode):
    runtime_handler, app, connection, binding_a, binding_b = bridge
    app.instance_config = SimpleNamespace(data={'plugin': {'enable': True}})
    app.deployment.mode = 'cloud' if mode == 'managed' else 'oss'
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector.handler = runtime_handler
    app.plugin_connector = connector
    execution_context = runtime_handler._execution_context(binding_a)
    setting_b = SimpleNamespace(
        installation_uuid=binding_b.installation_uuid,
        runtime_revision=binding_b.runtime_revision,
        artifact_digest=binding_b.artifact_digest,
        install_info={'_artifact_storage': 'tenant_binary_storage_v1'} if mode == 'managed' else {},
    )
    connector._setting_for_plugin = AsyncMock(return_value=(execution_context, setting_b))
    connector.require_workspace_context = AsyncMock(return_value=execution_context)
    file_bytes = b'parser document'
    app.rag_runtime_service = SimpleNamespace(get_file_stream=AsyncMock(return_value=file_bytes))
    inbound_context = binding_a
    if mode == 'legacy':
        inbound_context = workspace_context().for_installation(binding_a.installation_uuid)
        setting_a = SimpleNamespace(
            plugin_author='author-a',
            plugin_name='plugin-a',
            installation_uuid=binding_a.installation_uuid,
            runtime_revision=binding_a.runtime_revision,
            artifact_digest=binding_a.artifact_digest,
        )
        app.persistence_mgr.execute_async.return_value = SimpleNamespace(first=lambda: setting_a)
    expected = binding_b if mode == 'managed' else connector._legacy_oss_bridge_binding(execution_context)
    request = ActionRequest.make_request(
        101,
        PluginToRuntimeAction.INVOKE_PARSER.value,
        {'plugin_author': 'author-b', 'plugin_name': 'parser-b', 'storage_path': 'file-a'},
        inbound_context,
    )

    await runtime_handler._handle_action(request.model_dump())

    response = json.loads(connection.sent[-1])
    assert response['code'] == 0, response
    chunks = connection.requests[:-1]
    parse = connection.requests[-1]
    assert len(chunks) == 4
    assert all(chunk['action'] == CommonAction.FILE_CHUNK.value for chunk in chunks)
    assert parse['action'] == LangBotToRuntimeAction.PARSE_DOCUMENT.value
    assert all(request['context'] == expected.model_dump() for request in connection.requests)
    assert b''.join(base64.b64decode(chunk['data']['chunk_base64']) for chunk in chunks) == file_bytes
    assert {chunk['data']['file_key'] for chunk in chunks} == {parse['data']['context']['file_key']}
    connector._setting_for_plugin.assert_awaited_once_with('author-b', 'parser-b', require_enabled=True)
    assert runtime_handler.current_action_context is None
    assert runtime_handler.resolve_outbound_action_context(None) is None


@pytest.mark.asyncio
async def test_explicit_argument_overrides_scope_and_inbound_falls_back(bridge):
    runtime_handler, _, connection, binding_a, binding_b = bridge
    token = runtime_handler._current_action_context.set(binding_a)
    try:
        with runtime_handler.installation_scope(binding_b):
            await runtime_handler.call_action(
                LangBotToRuntimeAction.LIST_PARSERS, {}, action_context=binding_a.model_dump()
            )
        await runtime_handler.list_parsers()
    finally:
        runtime_handler._current_action_context.reset(token)
    assert [request['context'] for request in connection.requests] == [binding_a.model_dump()] * 2
    assert runtime_handler.resolve_outbound_action_context(None) is None


@pytest.mark.asyncio
async def test_explicit_none_scope_clears_inbound_and_restores_outer_scope(bridge):
    runtime_handler, _, connection, binding_a, binding_b = bridge
    token = runtime_handler._current_action_context.set(binding_a)
    try:
        with runtime_handler.installation_scope(binding_b):
            await runtime_handler.ping()
            await runtime_handler.list_parsers()
        await runtime_handler.list_parsers()
    finally:
        runtime_handler._current_action_context.reset(token)
    assert [request.get('context') for request in connection.requests] == [
        None,
        binding_b.model_dump(),
        binding_a.model_dump(),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [RuntimeError, asyncio.CancelledError])
async def test_scope_restores_after_exception_or_cancellation(bridge, failure):
    runtime_handler, _, connection, binding_a, binding_b = bridge
    with runtime_handler.installation_scope(binding_a):
        with pytest.raises(failure):
            with runtime_handler.installation_scope(binding_b):
                await runtime_handler.list_parsers()
                raise failure()
        await runtime_handler.list_parsers()
    await runtime_handler.list_parsers()
    assert [request.get('context') for request in connection.requests] == [
        binding_b.model_dump(),
        binding_a.model_dump(),
        None,
    ]


@pytest.mark.asyncio
async def test_concurrent_nested_scopes_do_not_leak_on_task_cancellation(bridge):
    runtime_handler, _, connection, binding_a, binding_b = bridge
    entered = asyncio.Event()
    release = asyncio.Event()

    async def cancelled_invocation():
        with runtime_handler.installation_scope(binding_b):
            await runtime_handler.list_parsers()
            entered.set()
            await release.wait()

    token = runtime_handler._current_action_context.set(binding_a)
    task = asyncio.create_task(cancelled_invocation())
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        with runtime_handler.installation_scope(None):
            await runtime_handler.list_parsers()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await runtime_handler.list_parsers()
    finally:
        runtime_handler._current_action_context.reset(token)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert [request.get('context') for request in connection.requests] == [
        binding_b.model_dump(),
        None,
        binding_a.model_dump(),
    ]
    assert runtime_handler.resolve_outbound_action_context(None) is None
