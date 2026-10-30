"""SDK 0.7.4 real child, WebSocket RPC, two slots and one component graph.

LangRAG/LongTermMemory: local Host vector/storage fixture only; no Cloud/sandbox
claim. Connectors: local Host storage/file fixture plus a loopback HTTP provider
fixture; no upstream/Cloud/sandbox claim.
"""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

from aiohttp import web
import websockets
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine
from langbot_plugin.cli.utils.page_components import discover_plugin_components
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.runtime.io.handler import Handler, ActionResponse
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction as R, PluginToRuntimeAction as P
from langbot_plugin.entities.io.context import InstallationBinding

CODE = Path(sys.argv[1]).resolve()
os.chdir(CODE)
sys.path.insert(0, str(CODE))

CONNECTORS = ('DifyDatasetsConnector', 'FastGPTConnector', 'RAGFlowConnector')

def binding(label):
    return InstallationBinding(instance_uuid='fixture-instance', workspace_uuid='workspace-'+label,
        placement_generation=1, installation_uuid='installation-'+label,
        runtime_revision=1, artifact_digest='a'*64)

async def child(url):
    discovery = ComponentDiscoveryEngine()
    manifest = discovery.load_component_manifest('manifest.yaml', no_save=True)
    # Probe shared eligibility without changing the dedicated release manifest.
    if CODE.name == 'LongTermMemory':
        manifest.execution.shared_runtime = 'shared-runtime-v1'
        manifest.execution.component_model = 'stateless-v1'
    components = discover_plugin_components(manifest, discovery)
    controller = PluginRuntimeController(manifest, components, False, '')
    original_attach = controller.initialize_slot
    identities = []
    async def attach(binding, settings):
        slot = await original_attach(binding, settings)
        identity = (id(slot.plugin_container.plugin_instance),
                    tuple(id(c.component_instance) for c in slot.plugin_container.components))
        identities.append(identity)
        if len(identities) == 2:
            assert identities[0] == identities[1], 'Slots have different object graphs'
            print('SAME_OBJECT_GRAPH=true', file=sys.stderr, flush=True)
        return slot
    async with websockets.connect(url) as ws:
        handler = PluginRuntimeHandler(WebSocketConnection(ws), controller.initialize)
        handler.plugin_container = controller.plugin_container
        handler._slot_initialize_callback = attach
        handler._slot_detach_callback = controller.detach_slot
        handler._slot_cancel_callback = controller.invalidate_slot
        controller.handler = handler
        await handler.run()

async def parent():
    stores = {label: {} for label in 'AB'}
    vectors = {label: {} for label in 'AB'}
    actions = []
    provider_calls = []

    async def provider(request):
        """Loopback stand-in for Dify/FastGPT/RAGFlow; echoes the caller's own credentials."""
        body = await request.read()
        auth = request.headers.get('Authorization', '')
        marker = auth.removeprefix('Bearer ')
        provider_calls.append((request.method, request.path_qs, auth, body))
        if request.method == 'DELETE':
            # FastGPT acknowledges with code 200; Dify accepts any 2xx; RAGFlow reads code 0.
            return web.json_response({'code': 200 if request.path.endswith('/collection/delete') else 0})
        if request.path.endswith('/retrieve'):
            return web.json_response({'records': [{'segment': {'id': 'seg', 'content': auth}, 'score': .8}]})
        if request.path.endswith('/searchTest'):
            return web.json_response({'code': 200, 'data': [{'id': 'seg', 'q': auth, 'a': 'answer', 'score': .8}]})
        if request.path.endswith('/retrieval'):
            return web.json_response({'code': 0, 'data': {'chunks': [{'id': 'seg', 'content': auth, 'similarity': .8}]}})
        if request.path.endswith('/create-by-file'):
            return web.json_response({'document': {'id': 'remote-doc-' + marker}})
        if request.path.endswith('/localFile'):
            return web.json_response({'code': 200, 'data': {'collectionId': 'remote-doc-' + marker,
                'results': {'insertLen': 2}}})
        if request.path.endswith(('/chunks', '/run_graphrag', '/run_raptor')):
            return web.json_response({'code': 0, 'data': {}})
        if request.method == 'POST' and request.path.endswith('/documents'):
            return web.json_response({'code': 0, 'data': [{'id': 'remote-doc-' + marker}]})
        # Dataset validation/listing.
        return web.json_response({'code': 0, 'data': []})

    # The loopback provider fixture is only needed by the connector branch.
    provider_runner = None
    base_url = ''
    if CODE.name in CONNECTORS:
        app = web.Application()
        app.router.add_route('*', '/{path:.*}', provider)
        provider_runner = web.AppRunner(app)
        await provider_runner.setup()
        site = web.TCPSite(provider_runner, '127.0.0.1', 0)
        await site.start()
        base_url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"

    connected = asyncio.get_running_loop().create_future()
    async def accept(ws):
        handler = Handler(WebSocketConnection(ws), file_storage_dir=Path('/tmp/ke-shared-probe-host'))
        def label():
            ctx = handler.current_action_context
            assert ctx in (binding('A'), binding('B')), ctx
            return ctx.workspace_uuid[-1]
        @handler.action(P.GET_PLUGIN_STORAGE_KEYS)
        async def keys(data):
            l = label(); actions.append((l, 'keys'))
            return ActionResponse.success({'keys': list(stores[l])})
        @handler.action(P.GET_PLUGIN_STORAGE)
        async def get(data):
            l = label(); actions.append((l, 'get'))
            if data['key'] not in stores[l]:
                stores[l][data['key']] = base64.b64encode(b'{}').decode()
            return ActionResponse.success({'value_base64': stores[l][data['key']]})
        @handler.action(P.SET_PLUGIN_STORAGE)
        async def set_value(data):
            l = label(); actions.append((l, 'set'))
            stores[l][data['key']] = data['value_base64']
            return ActionResponse.success({})
        @handler.action(P.GET_KNOWLEDEGE_FILE_STREAM)
        async def file_stream(data):
            # Per-binding fixture file: a binding must never read its sibling's bytes.
            l = label(); actions.append((l, 'file'))
            assert data['storage_path'] == 'fixture-file', data
            key = await host.send_file(b'private-' + l.encode(), '')
            return ActionResponse.success({'file_key': key})
        @handler.action(P.INVOKE_EMBEDDING)
        async def embed(data):
            l = label(); actions.append((l, 'embed'))
            return ActionResponse.success({'vectors': [[1.0] for _ in data['texts']]})
        @handler.action(P.VECTOR_UPSERT)
        async def upsert(data):
            l = label(); actions.append((l, 'upsert'))
            for id_, meta in zip(data['ids'], data['metadata']):
                vectors[l][id_] = {'id': id_, 'distance': .1, 'metadata': meta}
            return ActionResponse.success({})
        @handler.action(P.VECTOR_SEARCH)
        async def search(data):
            l = label(); actions.append((l, 'search'))
            return ActionResponse.success({'results': list(vectors[l].values())[:data['top_k']]})
        @handler.action(P.VECTOR_DELETE)
        async def delete(data):
            l = label(); actions.append((l, 'delete'))
            n = len(vectors[l]); vectors[l].clear()
            return ActionResponse.success({'count': n})
        connected.set_result(handler)
        await handler.run()
    async with websockets.serve(accept, '127.0.0.1', 0) as server:
        url = f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
        proc = await asyncio.create_subprocess_exec(sys.executable, __file__, str(CODE), '--child', url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, 'LANGBOT_PLUGIN_FILE_STORAGE_DIR': '/tmp/ke-shared-probe-child-files'})
        try:
            host = await asyncio.wait_for(connected, 15)
            async def call(label, action, data):
                return await host.call_action(action, data, action_context=binding(label), timeout=20)
            def settings(label):
                if CODE.name in CONNECTORS:
                    # Connectors declare no plugin config; the per-installation
                    # settings still differ between the two bindings.
                    return {'enabled': True, 'priority': 0 if label == 'A' else 1, 'plugin_config': {}}
                return {'enabled': True, 'priority': 0, 'plugin_config': {
                    'max_profile_traits': 1 if label == 'A' else 4,
                    'max_profile_preferences': 1 if label == 'A' else 4}}
            for label in 'AB':
                await call(label, R.ATTACH_PLUGIN_SLOT, {'plugin_settings': settings(label)})
            a = await call('A', R.GET_PLUGIN_SLOT_CONTAINER, {})
            b = await call('B', R.GET_PLUGIN_SLOT_CONTAINER, {})
            if CODE.name in CONNECTORS:
                assert a['priority'] != b['priority'], (a['priority'], b['priority'])
            else:
                assert a['plugin_config'] != b['plugin_config']
            if CODE.name == 'LangRAG':
                for label in 'AB':
                    result = await call(label, R.INGEST_DOCUMENT, {'context': {
                        'knowledge_base_id': 'same-kb', 'creation_settings': {'embedding_model_uuid': 'fixture-embedding'},
                        'file_object': {'metadata': {'filename': 'doc.txt', 'document_id': 'same-doc',
                            'knowledge_base_id': 'same-kb', 'file_size': 12, 'mime_type': 'text/plain'}, 'storage_path': 'fixture-file'},
                        'parsed_content': {'text': 'private-'+label}}})
                    assert result['status'] == 'completed', result
                for label in 'AB':
                    result = await call(label, R.RETRIEVE_KNOWLEDGE, {'retriever_name': '', 'retrieval_context': {
                        'query': 'fixture query', 'knowledge_base_id': 'same-kb',
                        'creation_settings': {'embedding_model_uuid': 'fixture-embedding'},
                        'retrieval_settings': {'top_k': 2}}})
                    assert result['total_found'] == 1, result
                    assert 'private-'+label in str(result), result
                for label in 'AB':
                    page = await call(label, R.PAGE_API, {'page_id': 'observability', 'endpoint': '/snapshot',
                        'method': 'GET', 'body': {}})
                    assert page['data']['counters']['ingest.total'] == 1, page
            elif CODE.name in CONNECTORS:
                def connector_config(label):
                    return {'api_base_url': base_url, 'api_key': label,
                        'dify_apikey': label, 'dataset_id': label, 'dataset_ids': label}
                for label in 'AB':
                    # Host notification for the same knowledge-base ID on each binding.
                    await call(label, R.ON_KB_CREATE, {'kb_id': 'same-kb', 'config': connector_config(label)})
                for label in 'AB':
                    result = await call(label, R.INGEST_DOCUMENT, {'context': {
                        'knowledge_base_id': 'same-kb', 'creation_settings': connector_config(label),
                        'file_object': {'metadata': {'filename': 'doc.txt', 'document_id': 'same-doc',
                            'knowledge_base_id': 'same-kb', 'file_size': 12, 'mime_type': 'text/plain'},
                            'storage_path': 'fixture-file'}}})
                    # The provider acknowledged a per-binding upstream document.
                    assert result['status'] == 'processing', result
                    assert result['document_id'] == 'remote-doc-'+label, result
                for label in 'AB':
                    result = await call(label, R.RETRIEVE_KNOWLEDGE, {'retriever_name': '', 'retrieval_context': {
                        'query': 'fixture query', 'knowledge_base_id': 'same-kb',
                        'creation_settings': connector_config(label), 'retrieval_settings': {'top_k': 2}}})
                    assert result['total_found'] == 1, result
                    other = 'B' if label == 'A' else 'A'
                    assert 'Bearer '+label in str(result), result
                    assert 'Bearer '+other not in str(result), result
                # Same Host storage key per binding, distinct durable per-binding value.
                for label in 'AB':
                    other = 'B' if label == 'A' else 'A'
                    key = 'ke.config.v1.' + hashlib.sha256(b'same-kb').hexdigest()
                    assert json.loads(base64.b64decode(stores[label][key]))['api_key'] == label
                    assert all('"'+other+'"' not in base64.b64decode(value).decode()
                        for value in stores[label].values()), stores[label]
                for label in 'AB':
                    # Delete resolves the stored per-binding credentials, not the sibling's.
                    result = await call(label, R.DELETE_DOCUMENT, {'kb_id': 'same-kb', 'document_id': 'same-doc'})
                    assert result['success'] is True, result
                for label in 'AB':
                    other = 'B' if label == 'A' else 'A'
                    own = [c for c in provider_calls if c[2] == 'Bearer '+label]
                    assert own, 'no provider call carried binding '+label+' credentials'
                    assert any(c[0] == 'DELETE' for c in own), own
                    assert 'remote-doc-'+label in str(own) and 'remote-doc-'+other not in str(own), own
                    assert 'private-'+label in str([c[3] for c in own])
                    assert 'private-'+other not in str([c[3] for c in own]), own
                # Each binding's ingest read its own Host file stream.
                assert [l for l, action in actions if action == 'file'] == ['A', 'B'], actions
            else:
                for label in 'AB':
                    page = await call(label, R.PAGE_API, {'page_id': 'memory_console', 'endpoint': '/summary',
                        'method': 'GET', 'body': {}})
                    assert page.get('data') and page['data']['plugin_config']['max_profile_traits'] == (1 if label == 'A' else 4), page
            summary = {'plugin': CODE.name, 'sdk': '0.7.4', 'worker_pid': proc.pid,
                'same_worker_two_workspace_slots': True, 'slot_settings_distinct': True,
                'successful_representative_invocation': True,
                'host_actions': actions, 'scope': 'real SDK child RPC, local Host fixture; no production/upstream/sandbox proof'}
            if CODE.name not in CONNECTORS:
                # Connectors declare no plugin config; their slots differ in
                # per-installation settings only.
                summary['slot_configs_distinct'] = True
            print(json.dumps(summary))
        finally:
            proc.terminate()
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), 5)
            except asyncio.TimeoutError:
                proc.kill(); stdout, stderr = await proc.communicate()
            if provider_runner is not None:
                await provider_runner.cleanup()
            # A terminated worker is SIGTERM on POSIX and exit code 1 on Windows.
            terminated = (0, -15) if os.name != 'nt' else (0, 1)
            if proc.returncode not in terminated:
                print('child stderr:', stderr.decode()[-3500:], file=sys.stderr)
            assert b'SAME_OBJECT_GRAPH=true' in stderr, stderr.decode()[-3500:]
            assert proc.returncode in terminated, proc.returncode

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[2] == '--child':
        asyncio.run(child(sys.argv[3]))
    else:
        asyncio.run(asyncio.wait_for(parent(), 60))
