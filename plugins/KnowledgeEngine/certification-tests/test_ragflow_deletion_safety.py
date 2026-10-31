"""RAGFlow connector: fail-closed fences and upstream-bound document mappings.

Host storage and the provider are local fixtures; no live deployment is
contacted. The behaviour asserted here is scoped to RAGFlow, so it lives in its
own file rather than in the shared per-connector fixtures.
"""
import asyncio
import json

import httpx
import pytest

from test_shared_state import (
    StorageFixture,
    bind,
    configuration,
    ingest_context,
    load_plugin,
)

from langbot_plugin.api.entities.builtin.rag import DocumentStatus

FENCE_KEY_PREFIX = 'ke.fence.v1.'


def fence_records(store):
    """Persisted fence markers that still require reconciliation."""
    return [json.loads(value) for key, value in store.data.items()
            if key.startswith(FENCE_KEY_PREFIX) and json.loads(value) is not None]


def provider(monkeypatch, handler):
    """Route the connector's HTTP through a recording mock transport."""
    calls = []

    async def service(request):
        calls.append(request)
        response = handler(request)
        if asyncio.iscoroutine(response):
            response = await response
        return response

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, 'AsyncClient',
        lambda **kw: client(transport=httpx.MockTransport(service), **kw),
    )
    return calls


def acknowledge(request):
    if request.method == 'POST' and request.url.path.endswith('/documents'):
        return httpx.Response(200, json={'code': 0, 'data': [{'id': 'upstream-1'}]})
    if request.method == 'DELETE':
        return httpx.Response(200, json={'code': 0})
    return httpx.Response(200, json={'code': 0, 'data': []})


def engine_with(monkeypatch, store, handler):
    calls = provider(monkeypatch, handler)
    pc, ec = load_plugin('RAGFlowConnector')
    engine = ec()
    plugin = bind(pc, store)

    async def read_file(path):
        return b'fixture file'

    plugin.get_knowledge_file_stream = read_file
    engine.plugin = plugin
    return engine, calls


def created_mapping(upstream_target, dataset_id='A'):
    return {'upstream_id': 'upstream-1', 'dataset_id': dataset_id,
            'api_base_url': upstream_target, 'status': 'created'}


@pytest.mark.asyncio
async def test_unreadable_fence_state_refuses_without_dispatch_and_recovers(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', created_mapping('https://fixture.invalid'))

    store.fail = True
    # An unreadable fence record is not the same as "no fences": the mutation is
    # refused before anything is dispatched.
    with pytest.raises(RuntimeError, match='Could not read persisted fences'):
        await engine.delete_document('kb', 'doc')
    assert calls == []

    store.fail = False
    # The failed read was not cached, so the next attempt re-reads and proceeds.
    assert await engine.delete_document('kb', 'doc') is True
    assert [request.method for request in calls] == ['DELETE']


@pytest.mark.asyncio
async def test_cancelled_upload_dispatch_fences_and_keeps_the_pending_mapping(monkeypatch):
    dispatched = asyncio.Event()

    async def handler(request):
        if request.method == 'POST' and request.url.path.endswith('/documents'):
            dispatched.set()
            await asyncio.sleep(30)
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    task = asyncio.create_task(engine.ingest(ingest_context(configuration('A'))))
    await asyncio.wait_for(dispatched.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The upload may have committed upstream, so the knowledge base stays fenced
    # until an operator reconciles it, in process and in durable storage.
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert [record['kb_id'] for record in fence_records(store)] == ['kb']
    assert [request.method for request in calls] == ['POST']
    mapping = await engine._load_document('kb', 'local-doc')
    assert mapping['status'] == 'pending', 'a cancelled upload must not advance the mapping'
    assert mapping['upstream_id'] == ''


@pytest.mark.asyncio
async def test_cancelled_delete_dispatch_fences_and_keeps_the_created_mapping(monkeypatch):
    dispatched = asyncio.Event()

    async def handler(request):
        if request.method == 'DELETE':
            dispatched.set()
            await asyncio.sleep(30)
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', created_mapping('https://fixture.invalid'))

    task = asyncio.create_task(engine.delete_document('kb', 'doc'))
    await asyncio.wait_for(dispatched.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert [record['kb_id'] for record in fence_records(store)] == ['kb']
    assert [request.method for request in calls] == ['DELETE']
    mapping = await engine._load_document('kb', 'doc')
    assert mapping['status'] == 'created', 'an unacknowledged delete must not tombstone the mapping'


@pytest.mark.asyncio
async def test_upload_rejection_leaves_no_fence(monkeypatch):
    async def handler(request):
        if request.method == 'POST' and request.url.path.endswith('/documents'):
            return httpx.Response(400, text='rejected')
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    result = await engine.ingest(ingest_context(configuration('A')))
    assert result.status == DocumentStatus.FAILED

    # The provider refused the request, which is an unambiguous answer: the
    # pre-dispatch intent was cleared again and the knowledge base is usable.
    assert not engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert fence_records(store) == []
    await engine.on_knowledge_base_create('kb', configuration('A'))


@pytest.mark.asyncio
async def test_mapping_of_another_upstream_is_refused_before_dispatch(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', created_mapping('https://other.invalid'))

    with pytest.raises(RuntimeError, match='Upstream target changed'):
        await engine.delete_document('kb', 'doc')
    assert calls == []


@pytest.mark.asyncio
async def test_mapping_without_a_recorded_upstream_is_refused_before_dispatch(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    await engine._save_config('kb', configuration('A'))
    # Historical mapping, written before the upstream target was recorded.
    await engine._save_document('kb', 'doc', {'upstream_id': 'upstream-1', 'dataset_id': 'A',
                                              'status': 'created'})

    with pytest.raises(RuntimeError, match='Upstream target changed'):
        await engine.delete_document('kb', 'doc')
    assert calls == []


@pytest.mark.asyncio
async def test_equivalent_configuration_of_the_recorded_upstream_is_accepted(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    config = configuration('A')
    result = await engine.ingest(ingest_context(config))
    assert result.status == DocumentStatus.PROCESSING
    mapping = await engine._load_document('kb', 'local-doc')
    assert mapping['api_base_url'] == 'https://fixture.invalid', 'the canonical target is recorded'

    # Casing, a default port and a trailing slash never distinguish deployments.
    await engine._save_config('kb', {**config, 'api_base_url': 'HTTPS://FIXTURE.INVALID:443/'})
    assert await engine.delete_document('kb', 'local-doc') is True
    assert [request.method for request in calls] == ['POST', 'POST', 'DELETE']


def fence_key_fault(shared_state, message):
    def fault(key):
        return RuntimeError(message) if key.startswith(shared_state.FENCE_KEY_PREFIX) else None
    return fault


@pytest.mark.asyncio
async def test_unpersistable_fence_aborts_the_upload_before_the_request(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    from components import shared_state

    store.write_fault = fence_key_fault(shared_state, 'fixture fence write rejected')

    # The pre-written protection cannot be persisted, so the upload must not be
    # dispatched at all.
    with pytest.raises(shared_state.FencePersistError, match='Could not persist fence'):
        await engine.ingest(ingest_context(configuration('A')))
    assert calls == []
    # A mutation that was never dispatched leaves no fence behind...
    assert not engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert fence_records(store) == []
    # ...only the durable pre-dispatch intent it had already recorded.
    assert (await engine._load_document('kb', 'local-doc'))['status'] == 'pending'


@pytest.mark.asyncio
async def test_unpersistable_fence_aborts_the_delete_before_the_request(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    from components import shared_state

    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', created_mapping('https://fixture.invalid'))

    store.write_fault = fence_key_fault(shared_state, 'fixture fence write rejected')
    with pytest.raises(shared_state.FencePersistError, match='Could not persist fence'):
        await engine.delete_document('kb', 'doc')
    assert calls == []
    assert not engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert fence_records(store) == []
    # The delete was never dispatched, so its mapping is still the recorded one.
    assert (await engine._load_document('kb', 'doc'))['status'] == 'created'


@pytest.mark.asyncio
async def test_upload_response_that_fails_validation_keeps_the_fence(monkeypatch):
    async def handler(request):
        if request.method == 'POST' and request.url.path.endswith('/documents'):
            # The provider answered 200 with a body the connector cannot decode:
            # the upload may have committed, so the outcome is unresolved.
            return httpx.Response(200, text='not json')
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    result = await engine.ingest(ingest_context(configuration('A')))
    assert result.status == DocumentStatus.FAILED

    # The whole mutation — response validation included — is inside the fence, so
    # the unparsable answer keeps the knowledge base fenced.
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert [record['kb_id'] for record in fence_records(store)] == ['kb']
    assert [request.method for request in calls] == ['POST']
    # The next mutation for this knowledge base is refused rather than dispatched
    # over the unresolved upload.
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.delete_document('kb', 'local-doc')


@pytest.mark.asyncio
async def test_unresolved_graphrag_keeps_the_fence_and_blocks_raptor(monkeypatch):
    async def handler(request):
        if request.url.path.endswith('/run_graphrag'):
            raise httpx.ReadTimeout('fixture graphrag timeout')
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    config = {**configuration('A'), 'auto_graphrag': True, 'auto_raptor': True}
    result = await engine.ingest(ingest_context(config))
    assert result.status == DocumentStatus.FAILED

    # The unknown GraphRAG outcome is unresolved: the chain stops there instead of
    # running RAPTOR, whose success would have cleared the shared fence.
    paths = [request.url.path for request in calls]
    assert paths == [
        '/api/v1/datasets/A/documents',
        '/api/v1/datasets/A/chunks',
        '/api/v1/datasets/A/run_graphrag',
    ], 'the chain stops at the unresolved GraphRAG trigger'
    assert not any(path.endswith('/run_raptor') for path in paths)
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert [record['kb_id'] for record in fence_records(store)] == ['kb']
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.on_knowledge_base_create('kb', configuration('A'))


@pytest.mark.asyncio
async def test_delete_cancellation_after_ack_before_the_tombstone_keeps_the_fence(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', created_mapping('https://fixture.invalid'))

    # The documented window: the provider has acknowledged the delete, the Host
    # tombstone has not been written yet.
    entered = asyncio.Event()
    release = asyncio.Event()
    record = engine._save_document

    async def gated_record(kb_id, host_document_id, value):
        if value.get('status') == 'deleted':
            entered.set()
            await release.wait()
        return await record(kb_id, host_document_id, value)

    monkeypatch.setattr(engine, '_save_document', gated_record)
    task = asyncio.create_task(engine.delete_document('kb', 'doc'))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()

    # The delete was acknowledged upstream but its Host record does not exist, so
    # the protection must not have been released: a retry would replay the delete.
    assert (await engine._load_document('kb', 'doc'))['status'] == 'created'
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb')
    assert [record['kb_id'] for record in fence_records(store)] == ['kb']
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.delete_document('kb', 'doc')
    assert [request.method for request in calls] == ['DELETE']


@pytest.mark.asyncio
async def test_later_success_never_clears_an_unresolved_fence(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    from components import shared_state

    plugin = engine.plugin
    await engine._state.fence(plugin, 'kb', 'earlier upload outcome unknown')

    ran = []

    async def later_mutation():
        ran.append(1)
        return 'dispatched'

    # The later mutation is refused instead of running and releasing the earlier
    # operation's fence as if its own success had resolved it.
    with pytest.raises(shared_state.FencedKnowledgeBaseError, match='unresolved'):
        await engine._state.dispatched(plugin, 'kb', later_mutation, 'later mutation')
    assert ran == []
    assert engine._state.is_fenced(engine._state.binding(plugin), 'kb')
    assert [record['kb_id'] for record in fence_records(store)] == ['kb']


def collection_context(config, collection_id):
    """An ingestion context whose collection id is not the knowledge-base id."""
    context = ingest_context(config)
    context.collection_id = collection_id
    return context


@pytest.mark.asyncio
async def test_differing_collection_and_knowledge_base_ids_share_one_identity(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    from components import shared_state

    plugin = engine.plugin
    binding = engine._state.binding(plugin)
    # The fence is taken for the knowledge base the Host names; an ingestion
    # context that carries a different collection id must observe the same one.
    await engine._state.fence(plugin, 'kb', 'earlier upload outcome unknown')
    context = collection_context(configuration('A'), 'collection-1')
    with pytest.raises(shared_state.FencedKnowledgeBaseError):
        await engine.ingest(context)
    assert calls == [], 'a fenced knowledge base dispatches nothing'

    await engine._state.clear_fence(plugin, 'kb')
    result = await engine.ingest(context)
    assert result.status == DocumentStatus.PROCESSING

    # One identity for the mapping too: it is written under the knowledge-base
    # key, so the deletion that names the knowledge base finds it.
    assert (await engine._load_document('kb', 'local-doc'))['upstream_id'] == 'upstream-1'
    assert await engine.delete_document('kb', 'local-doc') is True
    assert [request.method for request in calls] == ['POST', 'POST', 'DELETE']
    assert (await engine._load_document('kb', 'local-doc'))['status'] == 'deleted'
    assert not engine._state.is_fenced(binding, 'kb')


@pytest.mark.asyncio
async def test_delete_under_another_knowledge_base_never_adopts_its_mapping(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)

    # Knowledge base A's mapping and configuration name the upstream document;
    # knowledge base B has neither.
    cfg = configuration('A')
    await engine._save_config('A', cfg)
    await engine._save_document('A', 'shared-doc', created_mapping('https://fixture.invalid'))

    # Deleting under B must not resolve, copy or tombstone A's record: the
    # operation is refused with nothing dispatched and nothing written under B.
    assert await engine.delete_document('B', 'shared-doc') is False
    assert calls == []
    assert engine._document_key('B', 'shared-doc') not in store.data
    assert engine._key('B') not in store.data
    assert (await engine._load_document('A', 'shared-doc'))['status'] == 'created'

    # A's own delete still reaches the provider: B never consumed its record.
    assert await engine.delete_document('A', 'shared-doc') is True
    assert [request.method for request in calls] == ['DELETE']


@pytest.mark.asyncio
async def test_pending_record_of_another_knowledge_base_does_not_block_ingest(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)

    # A pending record under knowledge base A is A's upload intent, not B's.
    await engine._save_document('A', 'local-doc',
                                {'upstream_id': '', 'dataset_id': 'A',
                                 'api_base_url': 'https://fixture.invalid', 'status': 'pending'})
    before = store.data[engine._document_key('A', 'local-doc')]

    context = ingest_context(configuration('B'))
    context.knowledge_base_id = 'B'
    result = await engine.ingest(context)
    assert result.status == DocumentStatus.PROCESSING

    # B recorded only its own mapping, and A's pending record is untouched: B
    # neither treated A's intent as its own nor wrote under A.
    assert (await engine._load_document('B', 'local-doc'))['status'] == 'created'
    assert (await engine._load_document('A', 'local-doc'))['status'] == 'pending'
    assert store.data[engine._document_key('A', 'local-doc')] == before
    assert [request.method for request in calls] == ['POST', 'POST']


INGESTION_STEPS = [
    pytest.param('/documents', {}, id='upload'),
    pytest.param('/chunks', {}, id='parse'),
    pytest.param('/run_graphrag', {'auto_graphrag': True}, id='graphrag'),
    pytest.param('/run_raptor', {'auto_raptor': True}, id='raptor'),
]


@pytest.mark.asyncio
@pytest.mark.parametrize('status, fenced', [(503, True), (400, False)])
@pytest.mark.parametrize('suffix, extra', INGESTION_STEPS)
async def test_ingestion_failure_classification_on_every_step(
        monkeypatch, suffix, extra, status, fenced):
    async def handler(request):
        if request.url.path.endswith(suffix):
            return httpx.Response(status, text='fixture answer')
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    result = await engine.ingest(ingest_context({**configuration('A'), **extra}))
    assert result.status == DocumentStatus.FAILED

    # A gateway failure is not proof that the request was not applied, so the
    # knowledge base stays fenced; a rejection is a resolved answer.
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb') is fenced
    assert bool(fence_records(store)) is fenced

    if fenced:
        # The next mutation is refused instead of being dispatched over the
        # unresolved one.
        with pytest.raises(RuntimeError, match='fenced'):
            await engine.delete_document('kb', 'local-doc')
    else:
        # The rejection was resolved, so the knowledge base is usable again.
        await engine.delete_document('kb', 'local-doc')


@pytest.mark.asyncio
@pytest.mark.parametrize('status, fenced', [(503, True), (400, False)])
async def test_delete_failure_classification(monkeypatch, status, fenced):
    async def handler(request):
        if request.method == 'DELETE':
            return httpx.Response(status, text='fixture answer')
        return acknowledge(request)

    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, handler)
    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', created_mapping('https://fixture.invalid'))

    assert await engine.delete_document('kb', 'doc') is False
    assert engine._state.is_fenced(engine._state.binding(engine.plugin), 'kb') is fenced
    assert bool(fence_records(store)) is fenced
    assert (await engine._load_document('kb', 'doc'))['status'] == 'created'

    if fenced:
        with pytest.raises(RuntimeError, match='fenced'):
            await engine.delete_document('kb', 'doc')
        assert [request.method for request in calls] == ['DELETE']
    else:
        # The rejection released the fence, so the delete may be retried.
        assert await engine.delete_document('kb', 'doc') is False


@pytest.mark.asyncio
async def test_fence_snapshot_read_before_a_clear_is_discarded(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    from components import shared_state

    state, plugin = engine._state, engine.plugin
    binding = state.binding(plugin)
    await state.fence(plugin, 'kb', 'earlier upload outcome unknown')

    # The fence is read once for the installation, and the read is answered with
    # the marker that existed before the clear below lands.
    store.gate_read(shared_state._kb_fence_key('kb'))
    load = asyncio.create_task(state._load_fences(plugin, binding))
    await asyncio.wait_for(store.gate_entered.wait(), 5)
    await state.clear_fence(plugin, 'kb')
    assert not state.is_fenced(binding, 'kb')
    store.gate_release.set()
    await load

    # The snapshot taken before the clear is discarded instead of re-fencing the
    # knowledge base the operator just cleared.
    assert not state.is_fenced(binding, 'kb')

    async def operation():
        return 'ran'

    assert await state.run(plugin, 'kb', operation) == 'ran'


@pytest.mark.asyncio
async def test_fence_state_is_read_once_per_installation(monkeypatch):
    store = StorageFixture()
    engine, calls = engine_with(monkeypatch, store, acknowledge)
    from components import shared_state

    state, plugin = engine._state, engine.plugin
    # A persisted fence for another knowledge base of the same installation gives
    # the first load a marker to read, and so a window inside that read.
    await state.fence(plugin, 'other', 'earlier upload outcome unknown')
    store.gate_read(shared_state._kb_fence_key('other'))
    before = store.keys_reads

    async def operation():
        return 'ran'

    first = asyncio.create_task(state.run(plugin, 'kb', operation))
    await asyncio.wait_for(store.gate_entered.wait(), 5)
    second = asyncio.create_task(state.run(plugin, 'kb-2', operation))
    await asyncio.sleep(.05)
    store.gate_release.set()
    assert await asyncio.gather(first, second) == ['ran', 'ran']

    # Both knowledge bases share one installation: the persisted fence state was
    # read once for the pair, not once per knowledge base.
    assert store.keys_reads - before == 1
