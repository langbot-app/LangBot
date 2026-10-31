"""Real HTTPX requests against a FAKE loopback provider (not provider E2E)."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from aiohttp import web
from langbot_plugin.api.entities.builtin.rag import (
    RetrievalContext, IngestionContext, FileObject, FileMetadata, DocumentStatus,
)

from test_shared_state import load_plugin, bind, StorageFixture, CONNECTORS, configuration


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_fake_http_ingest_retrieve_restart_delete_contract(name):
    pc, ec = load_plugin(name)
    received = []
    async def fake_service(request):
        body = await request.read()
        auth = request.headers.get('Authorization')
        received.append((request.method, request.path, auth, body))
        await asyncio.sleep(.002)
        if request.path.endswith('/retrieve'):
            return web.json_response({'records': [{'segment': {'id': 'seg', 'content': auth}, 'score': .8}]})
        if request.path.endswith('/searchTest'):
            return web.json_response({'data': [{'id': 'seg', 'q': auth, 'a': 'answer', 'score': .8}]})
        if request.path.endswith('/retrieval'):
            return web.json_response({'code': 0, 'data': {'chunks': [{'id': 'seg', 'content': auth, 'similarity': .8}]}})
        if request.path.endswith('/create-by-file'):
            assert b'fixture file' in body
            return web.json_response({'document': {'id': 'remote-doc'}})
        if request.path.endswith('/localFile'):
            assert b'fixture file' in body
            return web.json_response({'code': 200, 'data': {'collectionId': 'remote-doc', 'results': {'insertLen': 2}}})
        if request.method == 'POST' and request.path.endswith('/documents'):
            assert b'fixture file' in body
            return web.json_response({'code': 0, 'data': [{'id': 'remote-doc'}]})
        if request.method == 'GET':
            return web.json_response({'code': 0, 'data': []})
        return web.json_response({'code': 200 if name == 'FastGPTConnector' else 0, 'data': {}})
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', fake_service)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    store = StorageFixture()
    plugin = bind(pc, store)
    async def read_file(path):
        assert path == 'fixture-file'
        return b'fixture file'
    plugin.get_knowledge_file_stream = read_file
    engine = ec()
    engine.plugin = plugin
    cfg = {**configuration('A'), 'api_base_url': f'http://127.0.0.1:{port}', 'auto_graphrag': True, 'auto_raptor': True}
    try:
        ctx = IngestionContext(file_object=FileObject(metadata=FileMetadata(filename='doc.txt', file_size=12, mime_type='text/plain', document_id='local-doc', knowledge_base_id='kb'), storage_path='fixture-file'), knowledge_base_id='kb', creation_settings=cfg)
        result = await engine.ingest(ctx)
        assert result.status == DocumentStatus.PROCESSING
        assert result.document_id == 'remote-doc'
        if name == 'RAGFlowConnector':
            assert any(x[1].endswith('/chunks') for x in received)
            assert any(x[1].endswith('/run_graphrag') for x in received)
            assert any(x[1].endswith('/run_raptor') for x in received)
        async def retrieve(i):
            config = {**cfg, 'api_key': f'T{i}', 'dify_apikey': f'T{i}'}
            return await engine.retrieve(RetrievalContext(query=f'query{i}', knowledge_base_id='kb', creation_settings=config, retrieval_settings={'top_k': 2}))
        outputs = await asyncio.gather(*(retrieve(i) for i in range(8)))
        for i, output in enumerate(outputs):
            assert output.total_found == 1
            assert f'Bearer T{i}' in output.results[0].content[0].text
            assert output.results[0].score == .8
        restarted = ec()
        restarted.plugin = bind(pc, store)
        assert await restarted.delete_document('kb', 'remote-doc')
        assert received[-1][2] == 'Bearer A'
        await restarted.on_knowledge_base_delete('kb')
        assert not await restarted.delete_document('kb', 'remote-doc')
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_http_has_total_deadline_not_only_inactivity_timeout(name, monkeypatch):
    pc, ec = load_plugin(name)
    from components import shared_state
    assert hasattr(shared_state, 'HTTP_TOTAL_TIMEOUT'), 'Require a total operation deadline'
    monkeypatch.setattr(shared_state, 'HTTP_TOTAL_TIMEOUT', .02)
    import httpx
    async def stalls(request):
        await asyncio.sleep(10)
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(stalls), **kw))
    engine = ec()
    engine.plugin = bind(pc, StorageFixture())
    output = await asyncio.wait_for(engine.retrieve(RetrievalContext(query='q', knowledge_base_id='kb', creation_settings=configuration('A'))), .5)
    assert output.total_found == 0
