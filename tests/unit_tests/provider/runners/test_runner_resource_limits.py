from __future__ import annotations

import asyncio
import threading
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.provider import runner
from langbot.pkg.provider.runners import (
    cozeapi,
    dashscopeapi,
    tboxapi,
    weknoraapi,
)


@pytest.mark.asyncio
async def test_blocking_provider_iterator_runs_outside_event_loop():
    release = threading.Event()

    def values():
        release.wait(timeout=2)
        yield 'ready'

    task = asyncio.create_task(anext(runner.iterate_sync(values())))
    await asyncio.sleep(0)
    assert not task.done()

    release.set()
    assert await asyncio.wait_for(task, timeout=1) == 'ready'


@pytest.mark.asyncio
async def test_sync_provider_iterator_has_event_limit():
    with pytest.raises(RuntimeError, match='event limit'):
        async for _ in runner.iterate_sync(iter([1, 2]), max_items=1):
            pass


@pytest.mark.asyncio
async def test_coze_runner_closes_request_scoped_client():
    request_runner = object.__new__(cozeapi.CozeAPIRunner)
    request_runner.coze = AsyncMock()

    await request_runner.aclose()

    request_runner.coze.close.assert_awaited_once()


@pytest.mark.parametrize(
    ('append', 'exception_type'),
    [
        (cozeapi._append_bounded, ValueError),
        (dashscopeapi._append_bounded, dashscopeapi.DashscopeAPIError),
        (tboxapi._append_bounded, tboxapi.TboxAPIError),
        (weknoraapi._append_bounded, weknoraapi.errors.WeKnoraAPIError),
    ],
)
def test_provider_accumulators_reject_oversized_output(append, exception_type):
    with pytest.raises(exception_type, match='exceeds the runtime limit'):
        append('x' * (1024 * 1024), 'y')
