from __future__ import annotations

import asyncio
import time

import pytest

from langbot.pkg.utils.event_loop_monitor import EventLoopLagMonitor


@pytest.mark.parametrize(
    'kwargs',
    [
        {'sample_interval_seconds': 0},
        {'sample_interval_seconds': float('inf')},
        {'recent_sample_count': 1},
        {'recent_sample_count': 3601},
    ],
)
def test_event_loop_monitor_rejects_unbounded_configuration(kwargs) -> None:
    with pytest.raises(ValueError):
        EventLoopLagMonitor(**kwargs)


def test_event_loop_monitor_snapshot_is_bounded_and_reports_p95() -> None:
    monitor = EventLoopLagMonitor(recent_sample_count=4)
    for lag_seconds in (0.001, 0.002, 0.003, 0.004, 0.100):
        monitor._record_lag_seconds(lag_seconds)

    snapshot = monitor.snapshot()

    assert snapshot == {
        'running': False,
        'samples_total': 5,
        'last_lag_ms': 100,
        'recent_p95_lag_ms': 100,
        'recent_max_lag_ms': 100,
        'max_lag_ms': 100,
    }
    assert len(monitor._recent_lag_ms) == 4


async def test_event_loop_monitor_start_and_stop_are_idempotent() -> None:
    monitor = EventLoopLagMonitor(
        sample_interval_seconds=0.001,
        recent_sample_count=4,
    )

    monitor.start()
    task = monitor._task
    monitor.start()
    assert monitor._task is task
    await asyncio.sleep(0.005)
    assert monitor.snapshot()['samples_total'] > 0
    assert monitor.snapshot()['running'] is True

    await monitor.stop()
    await monitor.stop()
    assert monitor.snapshot()['running'] is False
    assert task is not None and task.done()


async def test_event_loop_monitor_observes_real_scheduler_stall() -> None:
    monitor = EventLoopLagMonitor(
        sample_interval_seconds=0.005,
        recent_sample_count=8,
    )
    monitor.start()
    try:
        await asyncio.sleep(0.01)
        time.sleep(0.05)
        await asyncio.sleep(0.01)
        assert monitor.snapshot()['recent_max_lag_ms'] >= 35
    finally:
        await monitor.stop()
