import asyncio

import pytest

from langbot_plugin.runtime.plugin.worker_watchdog import WorkerWatchdog


def test_idle_worker_requires_failed_probe_not_missing_business_requests():
    monitor = WorkerWatchdog(timeout_seconds=90)
    assert not monitor.observe(False, now=100)
    assert not monitor.observe(False, now=189)
    assert monitor.observe(False, now=190)


def test_success_resets_continuous_failure_window():
    monitor = WorkerWatchdog(timeout_seconds=90)
    monitor.observe(False, now=100)
    assert not monitor.observe(True, now=189)
    assert not monitor.observe(False, now=190)
    assert not monitor.observe(False, now=279)
    assert monitor.observe(False, now=280)


@pytest.mark.asyncio
async def test_supervision_cancels_worker_on_liveness_failure():
    from langbot_plugin.runtime.plugin.worker_watchdog import supervise_liveness

    stopped = asyncio.Event()

    async def worker():
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def unhealthy():
        raise TimeoutError("worker unresponsive")

    task = asyncio.create_task(worker())
    await asyncio.sleep(0)
    with pytest.raises(TimeoutError):
        await supervise_liveness(task, unhealthy())
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_watchdog_reaps_real_child_before_failure_is_returned():
    import sys
    from langbot_plugin.runtime.plugin.worker_watchdog import supervise_liveness

    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time; time.sleep(60)"
    )

    async def worker():
        try:
            await process.wait()
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()

    async def hung_probe():
        await asyncio.Event().wait()

    task = asyncio.create_task(worker())
    monitor = WorkerWatchdog(timeout_seconds=0.01)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            supervise_liveness(
                task, monitor.watch(hung_probe, interval=0.001, probe_timeout=0.005)
            ),
            timeout=2,
        )
    assert process.returncode is not None
    assert task.done()


def test_rejects_invalid_timeout():
    for value in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            WorkerWatchdog(timeout_seconds=value)


@pytest.mark.asyncio
async def test_hung_probe_is_bounded_and_reports_timeout():
    async def probe():
        await asyncio.Event().wait()

    monitor = WorkerWatchdog(timeout_seconds=0.01)
    with pytest.raises(TimeoutError, match="worker unresponsive"):
        await asyncio.wait_for(
            monitor.watch(probe, interval=0.001, probe_timeout=0.005), timeout=1
        )


@pytest.mark.asyncio
async def test_cancellation_does_not_turn_into_restart():
    entered = asyncio.Event()

    async def probe():
        entered.set()
        await asyncio.Event().wait()

    monitor = WorkerWatchdog(timeout_seconds=90)
    task = asyncio.create_task(monitor.watch(probe, interval=0.001, probe_timeout=10))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
