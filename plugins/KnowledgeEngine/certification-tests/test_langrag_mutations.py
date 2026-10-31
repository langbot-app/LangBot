"""LangRAG mutation ordering against a detached, simulated Host vector commit."""
import asyncio
import pytest
from langbot_plugin.api.entities.builtin.rag import IngestionContext, FileMetadata, FileObject, ParseResult
from test_shared_state import load_plugin, bind, StorageFixture


def context():
    return IngestionContext(knowledge_base_id='kb', file_object=FileObject(
        metadata=FileMetadata(filename='file.txt', mime_type='text/plain', file_size=4, document_id='doc', knowledge_base_id='kb'),
        storage_path='unused'), parsed_content=ParseResult(text='test content'),
        creation_settings={'embedding_model_uuid': 'fixture-model'})


@pytest.mark.asyncio
async def test_cancelled_ingest_cannot_commit_after_delete():
    pc, ec = load_plugin('LangRAG')
    plugin = bind(pc, StorageFixture())
    await plugin.initialize()
    entered, release = asyncio.Event(), asyncio.Event()
    rows = []
    async def embed(*args):
        return [[1.0]]
    async def upsert(**kwargs):
        async def commit():
            entered.set()
            await release.wait()
            rows.extend(kwargs['ids'])
        await asyncio.shield(asyncio.create_task(commit()))
    async def delete(**kwargs):
        count = len(rows)
        rows.clear()
        return count
    plugin.invoke_embedding, plugin.vector_upsert, plugin.vector_delete = embed, upsert, delete
    engine = ec()
    engine.plugin = plugin
    task = asyncio.create_task(engine.ingest(context()))
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    deleted = asyncio.create_task(engine.delete_document('kb', 'doc'))
    try:
        await asyncio.sleep(.01)
        with pytest.raises(RuntimeError, match='fenced'):
            await deleted
    finally:
        release.set()
        await asyncio.gather(task, deleted, return_exceptions=True)
    # A detached Host may still commit; fenced state cannot claim safe deletion.
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.delete_document('kb', 'doc')


@pytest.mark.asyncio
async def test_ambiguous_vector_failure_fences_future_mutations():
    pc, ec = load_plugin('LangRAG')
    plugin = bind(pc, StorageFixture())
    await plugin.initialize()
    async def embed(*args):
        return [[1.0]]
    async def upsert(**kwargs):
        raise TimeoutError('fixture unknown remote commit outcome')
    plugin.invoke_embedding, plugin.vector_upsert = embed, upsert
    engine = ec()
    engine.plugin = plugin
    result = await engine.ingest(context())
    assert result.status.value == 'failed'
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.ingest(context())
