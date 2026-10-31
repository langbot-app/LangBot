"""Real LangRAG + SDK dispatch/proxy/WebSocket; explicitly simulated Host.

Run separately from LangRAG/tests, which installs SDK stubs. No Core DB, live
vector provider or production deployment is exercised here. The row fixture
models Core's explicit-True gate and a failed Host commit, not its ORM.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
import websockets
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.cli.utils.page_components import discover_plugin_components
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction as P,
    RuntimeToPluginAction as R,
)
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.errors import ActionCallError
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import ActionResponse, Handler
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

from test_shared_state import load_plugin


@pytest_asyncio.fixture
async def boundary(tmp_path, monkeypatch):
    # Clear prior candidate modules, then let the genuine SDK discover/instantiate.
    load_plugin('LangRAG')
    code = Path(__file__).resolve().parents[1] / 'LangRAG'
    monkeypatch.chdir(code)
    monkeypatch.syspath_prepend(str(code))
    monkeypatch.setenv('LANGBOT_PLUGIN_FILE_STORAGE_DIR', str(tmp_path / 'worker'))
    discovery = ComponentDiscoveryEngine()
    manifest = discovery.load_component_manifest('manifest.yaml', no_save=True)
    controller = PluginRuntimeController(
        manifest, discover_plugin_components(manifest, discovery), False, ''
    )
    scope = InstallationBinding(
        instance_uuid='fixture-instance', workspace_uuid='fixture-workspace',
        placement_generation=1, installation_uuid='fixture-installation',
        runtime_revision=1, artifact_digest='0' * 64,
    )
    state = SimpleNamespace(rows={}, store={}, calls=[], response=None)
    ready = asyncio.get_running_loop().create_future()

    async def connected(ws):
        worker = PluginRuntimeHandler(WebSocketConnection(ws), controller.initialize)
        controller.handler = worker
        worker.plugin_container = controller.plugin_container
        ready.set_result(worker)
        await worker.run()

    async with websockets.serve(connected, '127.0.0.1', 0) as server:
        async with websockets.connect(
            f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
        ) as ws:
            host = Handler(WebSocketConnection(ws), file_storage_dir=tmp_path / 'host')

            @host.action(P.GET_PLUGIN_STORAGE_KEYS)
            async def keys(data):
                return ActionResponse.success({'keys': list(state.store)})

            @host.action(P.GET_PLUGIN_STORAGE)
            async def get(data):
                return ActionResponse.success({'value_base64': state.store[data['key']]})

            @host.action(P.SET_PLUGIN_STORAGE)
            async def put(data):
                state.store[data['key']] = data['value_base64']
                return ActionResponse.success({})

            @host.action(P.GET_KNOWLEDEGE_FILE_STREAM)
            async def file_stream(data):
                # Empty external text currently falls back to the internal parser.
                assert data['storage_path'] == 'fixture-unused'
                key = await host.send_file(b'', 'txt', action_context=scope)
                return ActionResponse.success({'file_key': key})

            @host.action(P.VECTOR_DELETE)
            async def delete(data):
                assert host.current_action_context == scope
                state.calls.append(data)
                if state.response is not None:
                    return state.response
                # Authoritative, file/collection-scoped removal; counts real fixture rows.
                targets = [key for key, file_id in state.rows.items()
                           if key[0] == data['collection_id'] and file_id in data['file_ids']]
                for key in targets:
                    del state.rows[key]
                return ActionResponse.success({'count': len(targets)})

            task = asyncio.create_task(host.run())
            worker = await ready

            async def call(action, data):
                return await host.call_action(action, data, action_context=scope, timeout=5)

            state.call = call
            state.controller = controller
            try:
                await call(R.INITIALIZE_PLUGIN, {'plugin_settings': {
                    'enabled': True, 'priority': 0, 'plugin_config': {},
                }})
                yield state
            finally:
                await host.close()
                await worker.close()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await controller.cleanup_instances()


class HostRowFixture:
    """Core-compatible confirmation gate; simulated Host transaction outcome."""
    present = True

    async def delete(self, boundary, *, fail_commit=False):
        result = await boundary.call(R.DELETE_DOCUMENT, {'kb_id': 'kb', 'document_id': 'doc'})
        if result['success'] is not True:
            raise RuntimeError('engine did not confirm deletion')
        if fail_commit:
            raise RuntimeError('fixture Host commit failed')
        self.present = False


@pytest.mark.asyncio
async def test_empty_parsed_ingest_then_zero_vector_delete_confirms_host_removal(boundary):
    result = await boundary.call(R.INGEST_DOCUMENT, {'context': {
        'knowledge_base_id': 'kb', 'creation_settings': {},
        'file_object': {'metadata': {'filename': 'empty.txt', 'file_size': 0,
            'mime_type': 'text/plain', 'document_id': 'doc', 'knowledge_base_id': 'kb'},
            'storage_path': 'fixture-unused'},
        'parsed_content': {'text': ''},
    }})
    assert result['status'] == 'completed'
    assert result['document_id'] == 'doc'
    assert result['chunks_created'] == 0
    assert not boundary.rows
    row = HostRowFixture()
    await row.delete(boundary)
    assert not row.present
    event = (await boundary.controller.plugin_container.plugin_instance.telemetry.snapshot())['recent']['delete'][0]
    assert event['status'] == 'completed'
    assert event['deleted'] is True
    assert event['vectors_deleted'] == 0
    assert boundary.calls == [{'collection_id': 'kb', 'file_ids': ['doc'], 'filters': None}]


@pytest.mark.asyncio
async def test_retry_after_vector_delete_and_failed_host_commit_is_idempotent(boundary):
    boundary.rows.update({('kb', 'chunk'): 'doc', ('kb', 'other'): 'other-doc',
                          ('other-kb', 'chunk'): 'doc'})
    row = HostRowFixture()
    with pytest.raises(RuntimeError, match='fixture Host commit failed'):
        await row.delete(boundary, fail_commit=True)
    assert row.present
    assert boundary.rows == {('kb', 'other'): 'other-doc', ('other-kb', 'chunk'): 'doc'}
    await row.delete(boundary)
    assert not row.present
    # Another authoritative no-op delete must also confirm through SDK serialization.
    assert await boundary.call(R.DELETE_DOCUMENT, {'kb_id': 'kb', 'document_id': 'doc'}) == {'success': True}
    assert len(boundary.calls) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('count', [0, 1, 3])
async def test_nonnegative_integer_acknowledgement_confirms(boundary, count):
    boundary.response = ActionResponse.success({'count': count})
    assert await boundary.call(R.DELETE_DOCUMENT, {'kb_id': 'kb', 'document_id': 'doc'}) == {'success': True}


@pytest.mark.asyncio
@pytest.mark.parametrize('count', [-1, None, False, True, 0.0, 1.5, '0', '1', [], {}])
async def test_malformed_count_never_confirms_and_fences_mutations(boundary, count):
    boundary.response = ActionResponse.success({'count': count})
    row = HostRowFixture()
    with pytest.raises(ActionCallError, match='nonnegative integer'):
        await row.delete(boundary)
    assert row.present
    boundary.response = None
    with pytest.raises(ActionCallError, match='fenced'):
        await row.delete(boundary)
    assert len(boundary.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('response, message', [
    (ActionResponse.success({}), 'count'),
    (ActionResponse.error('fixture VectorStoreError'), 'fixture VectorStoreError'),
    (ActionResponse.error('fixture timeout; unknown remote outcome'), 'fixture timeout'),
])
async def test_unconfirmed_host_result_propagates_and_preserves_row(boundary, response, message):
    boundary.response = response
    row = HostRowFixture()
    with pytest.raises(ActionCallError, match=message):
        await row.delete(boundary)
    assert row.present
    boundary.response = None
    with pytest.raises(ActionCallError, match='fenced'):
        await row.delete(boundary)
    assert len(boundary.calls) == 1
