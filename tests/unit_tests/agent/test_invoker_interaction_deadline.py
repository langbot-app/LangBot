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
