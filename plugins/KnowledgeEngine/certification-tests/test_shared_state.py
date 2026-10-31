"""Real SDK objects; storage/HTTP are explicit local fixtures, not live services."""
import asyncio
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from langbot_plugin.api.entities.builtin.rag import (
    DocumentStatus,
    FileMetadata,
    FileObject,
    IngestionContext,
)

ROOT = Path(__file__).resolve().parents[1]
CONNECTORS = ['DifyDatasetsConnector', 'FastGPTConnector', 'RAGFlowConnector']


def load_plugin(name):
    # Runtime uses one process per installation. Clear package names for this test loader.
    for key in list(sys.modules):
        if key == 'components' or key.startswith('components.'):
            del sys.modules[key]
    sys.path.insert(0, str(ROOT / name))
    try:
        spec = importlib.util.spec_from_file_location('candidate_main', ROOT / name / 'main.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from importlib import import_module
        engine = import_module('components.knowledge_engine.' + ('langrag' if name == 'LangRAG' else 'engine'))
        return getattr(mod, name), getattr(engine, name)
    finally:
        sys.path.pop(0)


class StorageFixture:
    """Explicit fixture for Host's installation-bound storage, not production storage."""
    def __init__(self):
        self.data = {}
        self.fail = False
        # Optional ``key -> exception`` fault injection for one durable write.
        self.write_fault = None
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()
        # Host-read instrumentation: how many key listings were served, and
        # one-shot gates that suspend the next read of one key so a test can land
        # a concurrent write inside that reader's window.
        self.keys_reads = 0
        self.gates = {}
        self.gate_entered = asyncio.Event()
        self.gate_release = asyncio.Event()

    def gate_read(self, key):
        """Suspend the next ``get_plugin_storage(key)`` until ``gate_release``.

        The gated reader captures the value it was answered with before it
        blocks, so the caller can change that record while the read is in flight
        exactly like a response computed before a concurrent write. Only the
        first read of ``key`` is gated; later readers pass through.
        """
        self.gate_entered = asyncio.Event()
        self.gate_release = asyncio.Event()
        self.gates[key] = self.gate_entered

    async def get_plugin_storage_keys(self):
        if self.fail:
            raise RuntimeError('fixture storage offline')
        self.keys_reads += 1
        return list(self.data)

    async def get_plugin_storage(self, key):
        if self.fail:
            raise RuntimeError('fixture storage offline')
        value = self.data[key]
        entered = self.gates.pop(key, None)
        if entered is not None:
            entered.set()
            await self.gate_release.wait()
        return value

    async def set_plugin_storage(self, key, value):
        # A detached Host commit survives cancellation of the caller, like real RPC.
        async def commit():
            self.started.set()
            await self.release.wait()
            if self.write_fault is not None:
                fault = self.write_fault(key)
                if fault is not None:
                    raise fault
            if self.fail:
                raise RuntimeError('fixture ambiguous commit')
            self.data[key] = value
        await asyncio.shield(asyncio.create_task(commit()))


def bind(plugin_cls, storage):
    plugin = plugin_cls()
    for name in ['get_plugin_storage_keys', 'get_plugin_storage', 'set_plugin_storage']:
        setattr(plugin, name, getattr(storage, name))
    return plugin


def configuration(marker):
    return {'api_base_url': 'https://fixture.invalid', 'api_key': marker,
            'dify_apikey': marker, 'dataset_id': marker, 'dataset_ids': marker}


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_connector_restart_isolation_and_delete(name, monkeypatch):
    pc, ec = load_plugin(name)
    calls = []
    async def service(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'code': 0, 'data': []})
        return httpx.Response(200, json={'code': 200 if name == 'FastGPTConnector' else 0})
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(service), **kw))
    a, b = StorageFixture(), StorageFixture()
    ea, eb = ec(), ec()
    ea.plugin, eb.plugin = bind(pc, a), bind(pc, b)
    config = configuration('A')
    await ea.on_knowledge_base_create('same-kb', config)
    config['api_key'] = 'MUTATED'
    await eb.on_knowledge_base_create('same-kb', configuration('B'))
    restarted = ec()
    restarted.plugin = bind(pc, a)
    # No acknowledged ingestion mapping exists; guessing a provider ID is unsafe.
    assert await restarted.delete_document('same-kb', 'doc') is False
    assert await eb.delete_document('same-kb', 'doc') is False
    assert not any(request.method == 'DELETE' for request in calls)
    # Mappings record the upstream target they were created on; a delete only
    # replays against that same target.
    await restarted._save_document('same-kb', 'doc', {'upstream_id': 'upstream-A', 'dataset_id': 'A', 'status': 'created', 'api_base_url': 'https://fixture.invalid'})
    await eb._save_document('same-kb', 'doc', {'upstream_id': 'upstream-B', 'dataset_id': 'B', 'status': 'created', 'api_base_url': 'https://fixture.invalid'})
    assert await restarted.delete_document('same-kb', 'doc') is True
    assert calls[-1].headers['authorization'] == 'Bearer A'
    assert await eb.delete_document('same-kb', 'doc') is True
    assert calls[-1].headers['authorization'] == 'Bearer B'
    await restarted.on_knowledge_base_delete('same-kb')
    assert await restarted.delete_document('same-kb', 'doc') is False
    assert await eb.delete_document('same-kb', 'doc') is False


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_cancelled_config_commit_cannot_resurrect_deleted_kb(name):
    pc, ec = load_plugin(name)
    store = StorageFixture()
    engine = ec()
    engine.plugin = bind(pc, store)
    store.release.clear()
    # Empty credentials avoid the optional RAGFlow validation request.
    write = asyncio.create_task(engine.on_knowledge_base_create('kb', {'marker': 'A'}))
    try:
        await asyncio.wait_for(store.started.wait(), .3)
        write.cancel()
        await asyncio.sleep(0)
        write.cancel()
        delete = asyncio.create_task(engine.on_knowledge_base_delete('kb'))
        await asyncio.sleep(.01)
        # The dispatched Host commit already holds the lock and is settled before
        # release, so the delete is ordered behind it rather than fenced: a
        # settled commit is not an ambiguous mutation. Ordinary cancellation of
        # the caller therefore does not fence the knowledge base.
        assert not delete.done()
        store.release.set()
        with pytest.raises(asyncio.CancelledError):
            await write
        await delete
    finally:
        store.release.set()
        await asyncio.gather(write, return_exceptions=True)
    # The tombstone is the last acknowledged commit: the cancelled create cannot
    # resurrect the deleted knowledge base, and the survivor is not fenced.
    restarted = ec()
    restarted.plugin = bind(pc, store)
    assert await restarted._load_config('kb') is None
    assert await restarted.delete_document('kb', 'doc') is False
    await restarted.on_knowledge_base_create('kb', {'marker': 'B'})
    assert (await restarted._load_config('kb'))['marker'] == 'B'


@pytest.mark.asyncio
async def test_langrag_telemetry_is_per_plugin_and_survives_restart():
    pc, _ = load_plugin('LangRAG')
    sa, sb = StorageFixture(), StorageFixture()
    a, b = bind(pc, sa), bind(pc, sb)
    await a.initialize()
    await b.initialize()
    assert hasattr(a, 'telemetry'), 'Telemetry must belong to the installation plugin'
    await a.telemetry.record_delete(collection_id='same', document_id='private-A', status='completed', duration_ms=1)
    assert (await b.telemetry.snapshot())['recent']['delete'] == []
    metrics = await b.telemetry.prometheus()
    warning_line = next(line for line in metrics.splitlines() if line.startswith('langrag_alerts_active{') and 'severity="warning"' in line)
    assert warning_line.endswith(' 0'), 'SDK persistence must not report JSONL-disabled warning'
    a2 = bind(pc, sa)
    await a2.initialize()
    assert (await a2.telemetry.snapshot())['recent']['delete'][0]['document_id'] == 'private-A'
    await a2.telemetry.clear()
    a3 = bind(pc, sa)
    await a3.initialize()
    assert (await a3.telemetry.snapshot())['recent']['delete'] == []


@pytest.mark.asyncio
async def test_text_parser_is_offloop(monkeypatch):
    load_plugin('LangRAG')
    from components.knowledge_engine.parser import FileParser
    import threading
    parser = FileParser()
    main_thread = threading.get_ident()
    monkeypatch.setattr(parser, '_decode_text', lambda data: str(threading.get_ident()))
    for filename in ['doc.txt', 'doc.unknown']:
        assert await parser.parse(b'x', filename) != str(main_thread)


def ingest_context(config):
    return IngestionContext(
        file_object=FileObject(
            metadata=FileMetadata(filename='doc.txt', file_size=12, mime_type='text/plain',
                                  document_id='local-doc', knowledge_base_id='kb'),
            storage_path='fixture-file'),
        knowledge_base_id='kb', creation_settings=config,
    )


def bind_mock_http(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, 'AsyncClient',
        lambda **kw: client(transport=httpx.MockTransport(handler), **kw),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_deterministic_validation_error_does_not_fence(name):
    pc, ec = load_plugin(name)
    store = StorageFixture()
    engine = ec()
    engine.plugin = bind(pc, store)
    # Raised before any Host or provider call: deterministic, must not fence.
    with pytest.raises(ValueError, match='64 KiB'):
        await engine.on_knowledge_base_create('kb', {'blob': 'x' * 70000})
    await engine.on_knowledge_base_create('kb', {'marker': 'ok'})
    restarted = ec()
    restarted.plugin = bind(pc, store)
    assert (await restarted._load_config('kb'))['marker'] == 'ok'


class GatedStorageFixture(StorageFixture):
    """Suspends the first key listing so cancellation lands before any dispatch."""
    def __init__(self):
        super().__init__()
        self.keys_entered = asyncio.Event()
        self.keys_gate = asyncio.Event()

    async def get_plugin_storage_keys(self):
        self.keys_entered.set()
        await self.keys_gate.wait()
        return await super().get_plugin_storage_keys()


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_cancellation_before_dispatch_does_not_fence(name):
    pc, ec = load_plugin(name)
    store = GatedStorageFixture()
    engine = ec()
    engine.plugin = bind(pc, store)
    task = asyncio.create_task(engine.on_knowledge_base_create('kb', {'marker': 'A'}))
    await store.keys_entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    store.keys_gate.set()
    # No mutation was dispatched, so the knowledge base stays usable.
    await engine.on_knowledge_base_create('kb', {'marker': 'B'})
    assert (await engine._load_config('kb'))['marker'] == 'B'


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_ambiguous_provider_response_fences_only_that_knowledge_base(name, monkeypatch):
    pc, ec = load_plugin(name)

    async def service(request):
        # Provider reports success but omits the upstream id: dispatched, unknown.
        if request.url.path.endswith('/create-by-file'):
            return httpx.Response(200, json={'document': {}})
        if request.url.path.endswith('/localFile'):
            return httpx.Response(200, json={'code': 200, 'data': {'collectionId': ''}})
        return httpx.Response(200, json={'code': 0, 'data': []})

    bind_mock_http(monkeypatch, service)
    store = StorageFixture()
    engine = ec()
    plugin = bind(pc, store)

    async def read_file(path):
        return b'fixture file'

    plugin.get_knowledge_file_stream = read_file
    engine.plugin = plugin
    cfg = configuration('A')
    with pytest.raises(RuntimeError, match='reconciliation'):
        await engine.ingest(ingest_context(cfg))
    # Only the failing knowledge base is fenced; its sibling still works.
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.on_knowledge_base_create('kb', cfg)
    await engine.on_knowledge_base_create('other-kb', cfg)
    # The fence is persisted, so a restarted worker still refuses that KB only.
    restarted = ec()
    restarted.plugin = bind(pc, store)
    with pytest.raises(RuntimeError, match='fenced'):
        await restarted.on_knowledge_base_create('kb', cfg)
    assert (await restarted._load_config('other-kb')) is not None
    # Deleting the knowledge base is the operator path out of the fence.
    await restarted.on_knowledge_base_delete('kb')
    await restarted.on_knowledge_base_create('kb', cfg)


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_ambiguous_transport_failure_is_reported_and_fenced(name, monkeypatch):
    pc, ec = load_plugin(name)

    async def service(request):
        raise httpx.ReadTimeout('fixture timeout')

    bind_mock_http(monkeypatch, service)
    store = StorageFixture()
    engine = ec()
    plugin = bind(pc, store)

    async def read_file(path):
        return b'fixture file'

    plugin.get_knowledge_file_stream = read_file
    engine.plugin = plugin
    cfg = configuration('A')
    result = await engine.ingest(ingest_context(cfg))
    assert result.status == DocumentStatus.FAILED
    # The caller still gets a FAILED result, but the dispatched upload is unknown.
    with pytest.raises(RuntimeError, match='fenced'):
        await engine.on_knowledge_base_create('kb', cfg)


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS + ['LangRAG'])
async def test_installation_revocation_releases_process_local_state(name):
    pc, ec = load_plugin(name)
    plugin = pc()
    engine = ec()
    engine.plugin = plugin
    await engine.initialize()
    binding = ('workspace', 'installation')
    lock = asyncio.Lock()
    engine._state._locks[(binding, 'kb')] = lock
    engine._state._fenced_keys(binding).add('ke.fence.v1.deadbeef')
    engine._state._fence_loaded.add(binding)
    if hasattr(engine._state, '_fence_load_locks'):
        # The single-flight load lock and the fence generation belong to the
        # binding too, so a revoked installation must not keep a stale pair.
        engine._state._fence_load_locks[binding] = asyncio.Lock()
        engine._state._fence_generation[binding] = 3
    await plugin.on_installation_revoked(binding)
    assert (binding, 'kb') not in engine._state._locks
    assert binding not in engine._state._fenced
    assert binding not in engine._state._fence_loaded
    if hasattr(engine._state, '_fence_load_locks'):
        assert binding not in engine._state._fence_load_locks
        assert binding not in engine._state._fence_generation


@pytest.mark.asyncio
async def test_langrag_fence_is_scoped_to_one_collection_and_survives_restart():
    """One knowledge base's ambiguous mutation must not block its siblings."""

    _, ec = load_plugin('LangRAG')
    engine = ec()
    plugin = StorageFixture()
    engine.plugin = plugin
    await engine.initialize()
    binding = engine._state.binding(plugin)

    async def boom():
        raise RuntimeError('host offline after dispatch')

    async def ok():
        return 7

    with pytest.raises(RuntimeError, match='host offline'):
        await engine._state.mutate(plugin, 'kb-a', boom, 'Host vector_upsert outcome unknown')

    # Only the failing knowledge base is fenced.
    assert engine._state.is_fenced(binding, 'kb-a')
    assert not engine._state.is_fenced(binding, 'kb-b')
    with pytest.raises(RuntimeError, match='fenced'):
        await engine._state.run(plugin, 'kb-a', ok)
    assert await engine._state.mutate(plugin, 'kb-b', ok, 'unrelated') == 7

    # A restarted worker still refuses the fenced knowledge base.
    restarted = ec()
    restarted.plugin = plugin
    with pytest.raises(RuntimeError, match='fenced'):
        await restarted._state.run(plugin, 'kb-a', ok)
    assert not restarted._state.is_fenced(restarted._state.binding(plugin), 'kb-b')

    # Deleting the knowledge base clears the fence.
    await restarted._state.clear_fence(plugin, 'kb-a')
    assert await restarted._state.run(plugin, 'kb-a', ok) == 7
