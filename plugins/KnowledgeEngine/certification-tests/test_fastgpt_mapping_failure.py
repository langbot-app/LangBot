import pytest
import httpx

from test_shared_state import load_plugin, StorageFixture, bind, configuration, ingest_context, bind_mock_http


@pytest.mark.asyncio
async def test_uploaded_collection_mapping_failure_is_ambiguous(monkeypatch):
    pc, ec = load_plugin('FastGPTConnector')
    engine = ec()
    engine.plugin = bind(pc, StorageFixture())

    async def stream(path):
        return b'acceptance document'

    engine.plugin.get_knowledge_file_stream = stream
    original = engine._save_document

    async def save(kb, document, value):
        if value.get('status') == 'created':
            raise RuntimeError('Host mapping commit unavailable')
        return await original(kb, document, value)

    monkeypatch.setattr(engine, '_save_document', save)

    async def upstream(request):
        return httpx.Response(200, json={'code': 200, 'data': {'collectionId': 'real-response-id', 'results': {'insertLen': 1}}})

    bind_mock_http(monkeypatch, upstream)
    from components.shared_state import AmbiguousMutationError
    with pytest.raises(AmbiguousMutationError):
        await engine.ingest(ingest_context(configuration('A')))
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
