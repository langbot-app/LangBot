"""SDK binary helpers through secured ExecutionAPI and ApplicationAPI contracts."""

# ruff: noqa: F811
import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.storage.artifacts import ArtifactError
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.artifacts import ArtifactOperationError, ArtifactsProxy
from langbot_plugin.entities.io.errors import ActionCallError
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from tests.integration.plugin.test_execution_api_routing import test_host  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.sdk_core, pytest.mark.contract('artifact_workspace_routing')]
META = dict(
    id='art_' + 'a' * 32,
    name='file.bin',
    mime_type='application/octet-stream',
    size=2,
    digest='a' * 64,
    source='upload',
    lifecycle='temporary',
)


@pytest.fixture
def bridge(test_host):
    host = test_host
    permissions = {
        'workspace_operations': ['artifact.create', 'artifact.get', 'artifact.read', 'artifact.read_content'],
        'capabilities': [],
    }
    for field in ('permission_declaration', 'permission_grants', 'permission_snapshot'):
        setattr(host.setting, field, permissions.copy())
    host.ap.artifact_service = SimpleNamespace(
        create=AsyncMock(return_value=META),
        get=AsyncMock(return_value=META),
        read=AsyncMock(return_value={'metadata': META, 'content': b'\x00\xff'}),
    )

    class Bridge:
        async def call_action(self, action, data, timeout=180, **kwargs):
            response = await host.handler.actions[action.value](data)
            if response.code:
                raise ActionCallError(response.message, response.data)
            return response.data

    return host, Bridge()


async def test_sdk_roundtrip_preserves_binary_and_trusted_owner(bridge):
    host, transport = bridge
    proxy = LangBotAPIProxy(transport).artifacts
    item = await proxy.create('file.bin', b'\x00\xff')
    assert (await proxy.read(item.id)).content == b'\x00\xff'
    context = host.ap.artifact_service.create.await_args.args[0]
    assert context.principal.installation_uuid == host.binding.installation_uuid
    assert host.ap.artifact_service.create.await_args.kwargs['content'] == b'\x00\xff'
    assert context.workspace_uuid == host.binding.workspace_uuid


@pytest.mark.parametrize(
    'arguments',
    [
        {'filename': 'x', 'content_base64': '*invalid*'},
        {'filename': 'x', 'content_base64': 'YQ==', 'content': 'also'},
        {'filename': 'x', 'content_base64': base64.b64encode(b'x' * (256 * 1024 + 1)).decode()},
        {'filename': 'x', 'content_base64': 'YQ==', 'owner_id': 'forged'},
    ],
)
async def test_invalid_wire_payload_never_reaches_service(bridge, arguments):
    host, transport = bridge
    response = await transport.call_action(
        Action.CALL_APPLICATION_OPERATION,
        {'operation_id': 'artifact.create', 'arguments': arguments},
    )
    assert response['ok'] is False and response['error']['code'] == 'invalid_input'
    host.ap.artifact_service.create.assert_not_awaited()


async def test_service_error_and_cancellation_survive_bridge(bridge):
    host, transport = bridge
    proxy = LangBotAPIProxy(transport).artifacts
    host.ap.artifact_service.read.side_effect = ArtifactError('artifact_integrity_failed', 'Integrity failed', 422)
    with pytest.raises(ArtifactOperationError) as error:
        await proxy.read(META['id'])
    assert error.value.code == 'artifact_integrity_failed'
    host.ap.artifact_service.read.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await proxy.read(META['id'])


async def test_run_does_not_fall_back_to_installation_grant(bridge, monkeypatch):
    host, transport = bridge
    session = {
        'plugin_identity': 'author-a/plugin-a',
        'authorization': {'workspace_id': host.binding.workspace_uuid, 'workspace_operations': []},
    }
    registry = SimpleNamespace(get=AsyncMock(return_value=session))
    monkeypatch.setattr('langbot.pkg.plugin.agent_run_support.get_session_registry', lambda: registry)
    proxy = ArtifactsProxy(transport, 'run-123')
    with pytest.raises(ArtifactOperationError):
        await proxy.get(META['id'])
    host.ap.artifact_service.get.assert_not_awaited()
    session['authorization']['workspace_operations'] = [{'id': 'artifact.get'}]
    assert (await proxy.get(META['id'])).id == META['id']
    host.setting.permission_grants = {'workspace_operations': [], 'capabilities': []}
    with pytest.raises(ArtifactOperationError):
        await proxy.get(META['id'])


async def test_knowledge_artifact_read_revocation_blocks_binary_transfer(test_host):
    host = test_host
    entered, release = asyncio.Event(), asyncio.Event()

    async def read(context, storage_path, *, plugin_id):
        assert storage_path == 'artifact:opaque' and plugin_id == 'author-a/plugin-a'
        entered.set()
        await release.wait()
        return b'private knowledge'

    host.ap.rag_runtime_service = SimpleNamespace(get_file_stream=read)
    host.handler.send_file = AsyncMock(return_value='must-not-send')
    pending = asyncio.create_task(
        host.handler.actions['get_knowledge_file_stream']({'storage_path': 'artifact:opaque'})
    )
    await asyncio.wait_for(entered.wait(), 5)
    host.setting.enabled = False
    release.set()
    response = await pending
    assert response.code != 0
    host.handler.send_file.assert_not_awaited()


async def test_knowledge_artifact_read_cancel_does_not_start_transfer(test_host):
    host = test_host
    entered = asyncio.Event()

    async def read(context, storage_path, *, plugin_id):
        entered.set()
        await asyncio.Event().wait()

    host.ap.rag_runtime_service = SimpleNamespace(get_file_stream=read)
    host.handler.send_file = AsyncMock()
    pending = asyncio.create_task(
        host.handler.actions['get_knowledge_file_stream']({'storage_path': 'artifact:opaque'})
    )
    await asyncio.wait_for(entered.wait(), 5)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    host.handler.send_file.assert_not_awaited()
