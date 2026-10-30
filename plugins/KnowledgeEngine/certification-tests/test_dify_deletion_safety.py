"""Dify deletion safety: fail-closed fence reads, dispatch fencing, target binding.

Host storage and the HTTP transport are explicit local fixtures; no live service
is contacted. The plugin is loaded through the shared certification loader so the
bundled ``components`` package is exercised as shipped.
"""
import asyncio

import httpx
import pytest

from test_shared_state import StorageFixture, bind, configuration, load_plugin


def make_engine(storage):
    pc, ec = load_plugin('DifyDatasetsConnector')
    engine = ec()
    engine.plugin = bind(pc, storage)
    return engine


def patch_http(monkeypatch, handler):
    calls = []

    async def service(request):
        calls.append(request)
        result = handler(request)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, 'AsyncClient',
        lambda **kw: client(transport=httpx.MockTransport(service), **kw),
    )
    return calls


async def seed(engine, mapping_target='https://fixture.invalid', dataset_id='A'):
    await engine._save_config('kb', configuration('A'))
    await engine._save_document('kb', 'doc', {
        'upstream_id': 'upstream-A', 'dataset_id': dataset_id, 'status': 'created',
        'api_base_url': mapping_target,
    })


@pytest.mark.asyncio
async def test_fence_read_failure_refuses_without_remote_call_and_recovers(monkeypatch):
    calls = patch_http(monkeypatch, lambda request: httpx.Response(204))
    store = StorageFixture()
    engine = make_engine(store)
    await seed(engine)
    from components import shared_state
    binding = engine._state.binding(engine.plugin)

    store.fail = True
    with pytest.raises(shared_state.FenceStateUnavailableError, match='fence state'):
        await engine.delete_document('kb', 'doc')
    # Unknown fence state fails closed before any provider request.
    assert calls == []
    # The failure is not cached as a loaded binding, so the read is retried.
    assert binding not in engine._state._fence_loaded

    store.fail = False
    assert await engine.delete_document('kb', 'doc') is True
    assert [request.method for request in calls] == ['DELETE']


class BlockingDelete:
    def __init__(self):
        self.entered = asyncio.Event()
        self.gate = asyncio.Event()

    async def __call__(self, request):
        self.entered.set()
        await self.gate.wait()
        return httpx.Response(204)


@pytest.mark.asyncio
async def test_cancelled_delete_dispatch_keeps_fence_and_mapping(monkeypatch):
    transport = BlockingDelete()
    calls = patch_http(monkeypatch, transport)
    store = StorageFixture()
    engine = make_engine(store)
    await seed(engine)
    binding = engine._state.binding(engine.plugin)

    task = asyncio.create_task(engine.delete_document('kb', 'doc'))
    await asyncio.wait_for(transport.entered.wait(), 1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) == 1
    # Dispatched with an unknown outcome: the fence is kept.
    assert engine._state.is_fenced(binding, 'kb')
    # The remote delete was never acknowledged, so the mapping stays actionable.
    assert (await engine._load_document('kb', 'doc'))['status'] == 'created'

    restarted = make_engine(store)
    with pytest.raises(RuntimeError, match='fenced'):
        await restarted.delete_document('kb', 'doc')


@pytest.mark.asyncio
async def test_deterministic_delete_rejection_leaves_no_fence(monkeypatch):
    calls = patch_http(monkeypatch, lambda request: httpx.Response(404, text='missing'))
    store = StorageFixture()
    engine = make_engine(store)
    await seed(engine)
    binding = engine._state.binding(engine.plugin)

    assert await engine.delete_document('kb', 'doc') is False
    assert len(calls) == 1
    assert not engine._state.is_fenced(binding, 'kb')

    # A restarted worker still dispatches (rather than being fenced).
    restarted = make_engine(store)
    assert await restarted.delete_document('kb', 'doc') is False


@pytest.mark.asyncio
async def test_delete_rejects_changed_upstream_before_any_remote_call(monkeypatch):
    calls = patch_http(monkeypatch, lambda request: httpx.Response(204))
    store = StorageFixture()
    engine = make_engine(store)
    await seed(engine, mapping_target='https://old.invalid')

    # Current configuration points at a different upstream instance.
    with pytest.raises(RuntimeError, match='Upstream target changed'):
        await engine.delete_document('kb', 'doc')
    assert calls == []

    # Legacy mappings lacking a bound target are equally rejected, before dispatch.
    legacy_store = StorageFixture()
    legacy = make_engine(legacy_store)
    await legacy._save_config('kb', configuration('A'))
    await legacy._save_document('kb', 'doc', {
        'upstream_id': 'upstream-A', 'dataset_id': 'A', 'status': 'created',
    })
    with pytest.raises(RuntimeError, match='Upstream target changed'):
        await legacy.delete_document('kb', 'doc')
    assert calls == []
