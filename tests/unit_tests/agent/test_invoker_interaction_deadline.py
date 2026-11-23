"""Bounded Runner transport reads, deadlines, and cleanup."""

import asyncio
import time
from types import SimpleNamespace

import pytest

from langbot.pkg.agent.runner.errors import RunnerExecutionError
from langbot.pkg.agent.runner.invoker import RunnerInvoker


def invoke_results(results, deadline_at):
    connector = SimpleNamespace(is_enable_plugin=True, run_runner=lambda **kwargs: results)
    logger = SimpleNamespace(warning=lambda message: None, error=lambda message: None)
    invoker = RunnerInvoker(SimpleNamespace(plugin_connector=connector, logger=logger))
    descriptor = SimpleNamespace(id='test', plugin_author='test', plugin_name='test', runner_name='test')
    return invoker.invoke(descriptor, {'runtime': {'deadline_at': deadline_at}})


@pytest.mark.asyncio
async def test_ready_terminal_survives_slow_host_consumer(monkeypatch):
    now = 100.0
    monkeypatch.setattr('langbot.pkg.agent.runner.invoker.time.time', lambda: now)
    read_after_terminal = asyncio.Event()

    async def results():
        yield {'type': 'message.completed'}
        yield {'type': 'run.completed'}
        read_after_terminal.set()

    stream = invoke_results(results(), deadline_at=101.0)
    try:
        assert (await anext(stream))['type'] == 'message.completed'
        # Let the producer run while the Host processes the previous frame.
        await asyncio.sleep(0.01)
        now = 102.0
        assert (await anext(stream))['type'] == 'run.completed'
        assert not read_after_terminal.is_set()
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_prefetch_keeps_only_one_frame_and_closes_the_producer():
    reads = []
    closed = asyncio.Event()

    async def results():
        try:
            for index in range(10):
                reads.append(index)
                yield {'type': 'message.delta', 'index': index}
        finally:
            closed.set()

    stream = invoke_results(results(), deadline_at=time.time() + 1)
    assert (await anext(stream))['index'] == 0
    await asyncio.sleep(0.01)
    await stream.aclose()

    assert reads == [0, 1]
    assert closed.is_set()


@pytest.mark.asyncio
async def test_raw_terminal_allows_consumer_to_continue_after_validation_rejects_it():
    next_read = asyncio.Event()

    async def results():
        yield {'type': 'run.completed', 'protocol_version': 'invalid'}
        next_read.set()
        yield {'type': 'message.completed'}
        yield {'type': 'run.completed'}

    stream = invoke_results(results(), deadline_at=time.time() + 1)
    try:
        assert (await anext(stream))['protocol_version'] == 'invalid'
        await asyncio.sleep(0.01)
        assert not next_read.is_set()
        assert (await anext(stream))['type'] == 'message.completed'
        assert (await anext(stream))['type'] == 'run.completed'
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_malformed_result_type_is_left_for_host_validation():
    async def results():
        yield {'type': ['run.completed']}
        yield {'type': 'run.completed'}

    stream = invoke_results(results(), deadline_at=time.time() + 1)
    try:
        assert (await anext(stream))['type'] == ['run.completed']
        assert (await anext(stream))['type'] == 'run.completed'
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_late_producer_still_times_out_and_is_closed():
    gate = asyncio.Event()
    closed = asyncio.Event()

    async def results():
        try:
            yield {'type': 'message.completed'}
            await gate.wait()
            yield {'type': 'run.completed'}
        finally:
            closed.set()

    stream = invoke_results(results(), deadline_at=time.time() + 0.03)
    assert (await anext(stream))['type'] == 'message.completed'
    await asyncio.sleep(0.06)
    gate.set()
    with pytest.raises(RunnerExecutionError) as exc:
        await anext(stream)
    assert exc.value.error_code == 'runner.timeout'
    assert closed.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_pending_prefetch_is_closed_on_consumer_exit(cancel):
    reading = asyncio.Event()
    closed = asyncio.Event()

    async def results():
        try:
            yield {'type': 'message.delta'}
            reading.set()
            await asyncio.Event().wait()
        finally:
            closed.set()

    stream = invoke_results(results(), deadline_at=time.time() + 1)
    await anext(stream)
    task = asyncio.create_task(anext(stream)) if cancel else None
    await asyncio.wait_for(reading.wait(), timeout=0.2)
    if task is not None:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        await stream.aclose()
    assert closed.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize('close_consumer', [False, True])
async def test_failed_prefetch_is_retrieved_on_consumer_exit(close_consumer):
    failed = asyncio.Event()

    async def results():
        try:
            yield {'type': 'message.delta'}
            raise ValueError('producer failed')
        finally:
            failed.set()

    stream = invoke_results(results(), deadline_at=time.time() + 1)
    await anext(stream)
    await asyncio.wait_for(failed.wait(), timeout=0.2)
    if close_consumer:
        await stream.aclose()
    else:
        with pytest.raises(RunnerExecutionError, match='producer failed'):
            await anext(stream)


@pytest.mark.asyncio
async def test_next_result_survives_interaction_deadline_extension():
    gate = asyncio.Event()
    context = {'runtime': {'deadline_at': time.time() + 0.02}}

    async def results():
        await gate.wait()
        yield {'type': 'run.completed'}

    reader = RunnerInvoker(SimpleNamespace())
    task = asyncio.create_task(
        reader._next_with_deadline(
            results(),
            SimpleNamespace(id='test'),
            context,
        )
    )
    await asyncio.sleep(0.01)
    context['runtime']['deadline_at'] = time.time() + 0.1
    await asyncio.sleep(0.03)
    gate.set()

    assert (await task)['type'] == 'run.completed'
