"""Regression fixtures are local; no external model/parser/provider requests."""
import asyncio
import threading

import pytest

from test_shared_state import load_plugin, bind, StorageFixture, CONNECTORS


@pytest.mark.asyncio
async def test_offload_slot_is_held_through_repeated_cancellation():
    pc, _ = load_plugin('LangRAG')
    plugin = bind(pc, StorageFixture())
    assert hasattr(plugin, 'offload'), 'CPU parsing/chunking needs installation bounded offload'
    entered = threading.Event()
    release = threading.Event()
    count = 0
    lock = threading.Lock()
    def job():
        nonlocal count
        with lock:
            count += 1
            if count == 2:
                entered.set()
        release.wait(2)
        return 'done'
    tasks = [asyncio.create_task(plugin.offload.run(job)) for _ in range(5)]
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(.005)
        assert entered.is_set()
        tasks[0].cancel()
        await asyncio.sleep(.01)
        tasks[0].cancel()
        await asyncio.sleep(.01)
        assert count == 2, 'Cancelled waiters must not release running thread slots'
        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError)
        assert results[1:] == ['done'] * 4
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_parser_rejects_oversized_input_before_decode():
    load_plugin('LangRAG')
    from components.knowledge_engine.parser import FileParser
    with pytest.raises(ValueError, match='limit'):
        await FileParser().parse(b'x' * (16 * 1024 * 1024 + 1), 'doc.txt')


@pytest.mark.asyncio
@pytest.mark.parametrize('name', CONNECTORS)
async def test_connector_storage_failure_is_not_missing_and_refuses_mutations(name):
    pc, ec = load_plugin(name)
    store = StorageFixture()
    engine = ec()
    engine.plugin = bind(pc, store)
    store.fail = True
    # Unreadable fence state is "unknown", never "unfenced": the mutation is
    # refused with the Host failure instead of being dispatched.
    with pytest.raises(RuntimeError, match='offline'):
        await engine.delete_document('kb', 'doc')
    with pytest.raises(RuntimeError, match='offline'):
        await engine.on_knowledge_base_create('kb', {})
    assert not store.data
    # The unreadable state is not cached either: once Host storage answers, the
    # same mutation is retried and proceeds rather than staying refused.
    store.fail = False
    await engine.on_knowledge_base_create('kb', {})
    assert store.data


@pytest.mark.asyncio
async def test_telemetry_cancellation_clear_and_failure_fencing():
    pc, _ = load_plugin('LangRAG')
    store = StorageFixture()
    plugin = bind(pc, store)
    await plugin.initialize()
    store.release.clear()
    task = asyncio.create_task(plugin.telemetry.record_delete(collection_id='kb', document_id='old', status='completed', duration_ms=1))
    await store.started.wait()
    task.cancel()
    clear = asyncio.create_task(plugin.telemetry.clear())
    await asyncio.sleep(.01)
    with pytest.raises(RuntimeError, match='fenced'):
        await clear
    store.release.set()
    await asyncio.gather(task, return_exceptions=True)
    other = bind(pc, store)
    await other.initialize()
    # A fresh reader may see the detached commit, but a failed clear cannot
    # acknowledge deletion or introduce a later event.
    assert all(event['document_id'] != 'new' for event in (await other.telemetry.snapshot())['recent']['delete'])
    store.fail = True
    with pytest.raises(RuntimeError, match='fenced'):
        await plugin.telemetry.record_delete(collection_id='kb', document_id='new', status='completed', duration_ms=1)
    with pytest.raises(RuntimeError, match='fenced'):
        await plugin.telemetry.snapshot()
    store.fail = False
    with pytest.raises(RuntimeError, match='fenced'):
        await plugin.telemetry.clear()
    assert all(event['document_id'] != 'new' for event in (await other.telemetry.snapshot())['recent']['delete'])
