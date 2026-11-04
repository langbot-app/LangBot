"""Deadline behavior while a Runner blocks on a Host interaction."""

import asyncio
import time
from types import SimpleNamespace

import pytest

from langbot.pkg.agent.runner.invoker import RunnerInvoker


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


@pytest.mark.asyncio
async def test_buffered_transport_stall_is_not_runner_timeout(monkeypatch):
    from unittest.mock import Mock
    from langbot.pkg.agent.runner import invoker as module
    from langbot.pkg.agent.runner.errors import RunnerExecutionError
    from langbot.pkg.agent.runner.stream_receipts import RunnerStreamReceipts

    context = {'runtime': {'deadline_at': time.time() - 1}}
    receipts = RunnerStreamReceipts(context)
    receipts.arrivals.append(receipts.deadline - 1)
    monkeypatch.setattr(module, '_BUFFERED_READ_TIMEOUT', 0.01)
    closed = []

    async def results():
        try:
            await asyncio.Event().wait()
            yield {}
        finally:
            closed.append(True)

    reader = RunnerInvoker(SimpleNamespace(logger=Mock()))
    stream = results()
    with pytest.raises(RunnerExecutionError) as exc:
        await reader._next_with_deadline(stream, SimpleNamespace(id='test'), context, receipts)
    await stream.aclose()
    assert exc.value.error_code == 'host.consume_timeout'
    assert closed == [True]
