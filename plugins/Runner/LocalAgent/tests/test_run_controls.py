"""Regression tests for local run controls, using genuine SDK contexts."""

from __future__ import annotations

import asyncio

import pytest

from components.runner.default import RunDeadline, RunInterruptChecker
from tests.test_runner import make_context


@pytest.mark.asyncio
async def test_slow_ledger_does_not_delay_chunks_or_deadline():
    calls = 0

    class SlowLedger:
        async def run_get(self, run_id):
            nonlocal calls
            calls += 1
            await asyncio.sleep(10)

    context = make_context()
    context.context.available_apis.run_get = True
    async with RunInterruptChecker(SlowLedger(), context) as checker:
        for _ in range(200):
            assert await checker.wait_for(asyncio.sleep(0, result="chunk"), deadline=RunDeadline(0.1)) == "chunk"
        assert calls == 1
        with pytest.raises(asyncio.TimeoutError):
            await checker.wait_for(asyncio.sleep(10), deadline=RunDeadline(0.02))
    assert checker._watcher is None


@pytest.mark.asyncio
async def test_operation_timeout_is_not_mistaken_for_poll_timeout():
    checker = RunInterruptChecker(None, make_context())
    operation_error = asyncio.TimeoutError("operation itself timed out")

    async def operation():
        raise operation_error

    with pytest.raises(asyncio.TimeoutError) as caught:
        await checker.wait_for(operation(), deadline=RunDeadline(0.02))

    assert caught.value is operation_error


@pytest.mark.asyncio
async def test_operation_timeout_propagates_without_deadline_when_polling():
    class RunLedgerFixture:
        async def run_get(self, run_id):
            # Give the enclosing test timeout a chance to stop a regression loop.
            await asyncio.sleep(0)
            return {"run_id": run_id, "status": "running"}

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(RunLedgerFixture(), context)
    operation_error = asyncio.TimeoutError("operation itself timed out")

    async def operation():
        raise operation_error

    with pytest.raises(asyncio.TimeoutError) as caught:
        await asyncio.wait_for(checker.wait_for(operation()), timeout=0.25)

    assert caught.value is operation_error


@pytest.mark.asyncio
async def test_watcher_shares_boundary_observation_but_next_boundary_is_fresh():
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class Ledger:
        async def run_get(self, run_id):
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return {"status": "cancelled" if calls > 1 else "running"}

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(Ledger(), context)
    first = asyncio.create_task(checker.is_cancelled(force=True))
    await started.wait()
    second = asyncio.create_task(checker.is_cancelled(force=True, coalesce=True))
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.gather(first, second) == [False, False]
    assert calls == 1
    assert await checker.is_cancelled(force=True)
    assert calls == 2


@pytest.mark.asyncio
async def test_watcher_shares_initial_boundary_and_still_cancels_slow_operation():
    from components.runner.default import RunCancelledError

    calls = 0
    stopped = asyncio.Event()

    class Ledger:
        async def run_get(self, run_id):
            nonlocal calls
            calls += 1
            return {"status": "cancelled" if calls > 1 else "running"}

    async def operation():
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(Ledger(), context, interval_seconds=0.1)
    async with checker:
        assert not await checker.is_cancelled(force=True)
        await asyncio.sleep(0)
        assert calls == 1
        with pytest.raises(RunCancelledError):
            await asyncio.wait_for(checker.wait_for(operation()), timeout=0.5)
    assert calls == 2
    assert stopped.is_set()
    assert checker._watcher is None


@pytest.mark.asyncio
async def test_external_cancel_closes_inflight_ledger_request():
    started = asyncio.Event()
    stopped = asyncio.Event()

    class Ledger:
        async def run_get(self, run_id):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(Ledger(), context)
    poll = asyncio.create_task(checker.is_cancelled(force=True))
    await started.wait()
    poll.cancel()
    with pytest.raises(asyncio.CancelledError):
        await poll
    assert stopped.is_set()
    assert not checker._check_lock.locked()


@pytest.mark.asyncio
async def test_forced_boundary_refreshes_without_waiting_for_stale_watcher():
    started = asyncio.Event()
    release = asyncio.Event()
    cancelled = False
    calls = 0

    class Ledger:
        async def run_get(self, run_id):
            nonlocal calls
            calls += 1
            snapshot = {"status": "cancelled" if cancelled else "running"}
            if calls == 1:
                started.set()
                await release.wait()
            return snapshot

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(Ledger(), context)
    watcher = asyncio.create_task(checker.is_cancelled(force=True, coalesce=True))
    try:
        await started.wait()
        cancelled = True
        assert await asyncio.wait_for(checker.is_cancelled(force=True), timeout=0.2)
        assert not watcher.done()
        assert calls == 2
    finally:
        release.set()
        await watcher
    # A late running snapshot cannot clear the observed cancellation.
    assert await checker.is_cancelled()


@pytest.mark.asyncio
async def test_background_and_boundary_polls_never_exceed_two_inflight_requests():
    inflight = 0
    peak = 0

    class Ledger:
        async def run_get(self, run_id):
            nonlocal inflight, peak
            inflight += 1
            peak = max(peak, inflight)
            try:
                await asyncio.sleep(0.01)
                return {"status": "running"}
            finally:
                inflight -= 1

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(Ledger(), context)
    await asyncio.gather(*(checker.is_cancelled(force=True, coalesce=bool(index % 2)) for index in range(20)))
    assert peak <= 2
    assert inflight == 0


@pytest.mark.asyncio
async def test_watcher_retries_when_overlapping_boundary_failed():
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class Ledger:
        async def run_get(self, run_id):
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                await release.wait()
                raise OSError("ledger unavailable")
            return {"status": "cancelled"}

    context = make_context()
    context.context.available_apis.run_get = True
    checker = RunInterruptChecker(Ledger(), context)
    boundary = asyncio.create_task(checker.is_cancelled(force=True))
    await started.wait()
    watcher = asyncio.create_task(checker.is_cancelled(force=True, coalesce=True))
    await asyncio.sleep(0)
    release.set()
    assert await watcher
    await boundary
    assert calls == 2
