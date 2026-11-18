from __future__ import annotations

import asyncio

import pytest

from langbot_plugin.entities.io.context import PluginWorkerPolicy
from typing import cast
from langbot_plugin.runtime.plugin.restart_coordinator import (
    PluginRestartCoordinator,
)


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    async def _poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(_poll(), timeout=timeout)


def _policy(**overrides) -> PluginWorkerPolicy:
    values = {
        "max_cpus": 1.0,
        "max_memory_mb": 512,
        "max_pids": 128,
        "max_open_files": 256,
        "max_file_size_mb": 512,
        "max_concurrent_restarts": 2,
        "restart_failure_threshold": 2,
        "restart_failure_window_seconds": 1.0,
        "restart_circuit_open_seconds": 0.02,
    }
    values.update(overrides)
    return PluginWorkerPolicy(**values)


async def test_restart_launches_are_globally_bounded():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(_policy())

    first = await coordinator.acquire()
    second = await coordinator.acquire()
    third_task = asyncio.create_task(coordinator.acquire())
    await asyncio.sleep(0)

    assert not third_task.done()
    assert coordinator.snapshot()["active_launches"] == 2

    first.mark_ready()
    third = await asyncio.wait_for(third_task, timeout=1)

    assert coordinator.snapshot()["active_launches"] == 2

    await second.abandon()
    await third.abandon()
    assert coordinator.snapshot()["active_launches"] == 0


async def test_failure_circuit_is_scoped_to_installation():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=2,
            restart_failure_threshold=1,
            restart_circuit_open_seconds=10.0,
        )
    )

    failed = await coordinator.acquire("installation-a")
    await failed.record_failure()

    blocked_same_installation = asyncio.create_task(
        coordinator.acquire("installation-a")
    )
    await _wait_until(lambda: coordinator.snapshot()["gate_waiters"] == 1)
    assert not blocked_same_installation.done()

    other_installation = await asyncio.wait_for(
        coordinator.acquire("installation-b"),
        timeout=1,
    )

    snapshot = coordinator.snapshot()
    assert snapshot["state"] == "open"
    assert snapshot["open_circuits"] == 1
    assert snapshot["active_launches"] == 1

    blocked_same_installation.cancel()
    await asyncio.gather(blocked_same_installation, return_exceptions=True)
    await other_installation.abandon()


async def test_open_installation_circuit_wait_does_not_hold_launch_slot():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
            restart_circuit_open_seconds=10.0,
        )
    )

    failed = await coordinator.acquire("installation-a")
    await failed.record_failure()

    blocked_same_installation = asyncio.create_task(
        coordinator.acquire("installation-a")
    )
    await _wait_until(lambda: coordinator.snapshot()["gate_waiters"] == 1)

    other_installation = await asyncio.wait_for(
        coordinator.acquire("installation-b"),
        timeout=1,
    )

    assert coordinator.snapshot()["active_launches"] == 1

    blocked_same_installation.cancel()
    await asyncio.gather(blocked_same_installation, return_exceptions=True)
    await other_installation.abandon()


async def test_failure_threshold_opens_circuit_and_one_probe_closes_it():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(_policy())

    first = await coordinator.acquire()
    await first.record_failure()
    second = await coordinator.acquire()
    await second.record_failure()

    snapshot = coordinator.snapshot()
    assert snapshot["state"] == "open"
    assert snapshot["circuit_open_total"] == 1

    probe_task = asyncio.create_task(coordinator.acquire())
    probe = await asyncio.wait_for(probe_task, timeout=1)
    assert probe.is_half_open_probe is True

    waiting_task = asyncio.create_task(coordinator.acquire())
    await asyncio.sleep(0)
    assert not waiting_task.done()

    probe.mark_ready()
    await probe.mark_stable()
    admitted = await asyncio.wait_for(waiting_task, timeout=1)

    snapshot = coordinator.snapshot()
    assert snapshot["state"] == "closed"
    assert snapshot["failures_in_window"] == 0

    await admitted.abandon()


async def test_failed_half_open_probe_reopens_circuit():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
        )
    )

    failed = await coordinator.acquire()
    await failed.record_failure()
    probe = await asyncio.wait_for(coordinator.acquire(), timeout=1)
    assert probe.is_half_open_probe is True

    await probe.record_failure()

    snapshot = coordinator.snapshot()
    assert snapshot["state"] == "open"
    assert snapshot["restart_failures_total"] == 2
    assert snapshot["circuit_open_total"] == 2


async def test_abandoned_probe_releases_slot_without_counting_failure():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
        )
    )

    failed = await coordinator.acquire()
    await failed.record_failure()
    probe = await asyncio.wait_for(coordinator.acquire(), timeout=1)
    failures_before = coordinator.snapshot()["restart_failures_total"]

    await probe.abandon()
    replacement_probe = await asyncio.wait_for(coordinator.acquire(), timeout=1)

    assert replacement_probe.is_half_open_probe is True
    assert coordinator.snapshot()["restart_failures_total"] == failures_before

    await replacement_probe.abandon()


async def test_repeated_cancellation_cannot_strand_half_open_probe():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
            restart_circuit_open_seconds=0.01,
        )
    )
    failed = await coordinator.acquire("installation-a")
    await failed.record_failure()
    probe = await asyncio.wait_for(
        coordinator.acquire("installation-a"),
        timeout=1,
    )
    assert probe.is_half_open_probe is True

    await coordinator._state_lock.acquire()
    abandon_task = asyncio.create_task(probe.abandon())
    await asyncio.sleep(0)
    abandon_task.cancel()
    await asyncio.sleep(0)
    abandon_task.cancel()
    coordinator._state_lock.release()

    with pytest.raises(asyncio.CancelledError):
        await abandon_task
    assert coordinator.snapshot()["half_open_probe_inflight"] is False

    replacement = await asyncio.wait_for(
        coordinator.acquire("installation-a"),
        timeout=1,
    )
    await replacement.abandon()


async def test_cancelled_acquire_does_not_leak_launch_slot():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
        )
    )
    await coordinator._state_lock.acquire()
    acquire_task = asyncio.create_task(coordinator.acquire())
    await asyncio.sleep(0)
    assert (
        coordinator._launch_semaphore is not None
        and not coordinator._launch_semaphore.locked()
    )

    acquire_task.cancel()
    coordinator._state_lock.release()
    with pytest.raises(asyncio.CancelledError):
        await acquire_task

    assert coordinator.snapshot()["active_launches"] == 0
    replacement = await asyncio.wait_for(coordinator.acquire(), timeout=1)
    await replacement.abandon()


async def test_open_circuit_bounds_cooldown_waiters_and_timers():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=2,
            restart_failure_threshold=1,
            restart_circuit_open_seconds=0.2,
        )
    )
    failed = await coordinator.acquire()
    await failed.record_failure()

    waiting = [asyncio.create_task(coordinator.acquire()) for _ in range(100)]
    await _wait_until(lambda: cast(int, coordinator.snapshot()["gate_waiters"]) >= 2)

    snapshot = coordinator.snapshot()
    assert snapshot["active_launches"] == 0
    assert snapshot["gate_waiters"] == 2
    assert sum(task.done() for task in waiting) == 0

    for task in waiting:
        task.cancel()
    await asyncio.gather(*waiting, return_exceptions=True)

    assert coordinator.snapshot()["active_launches"] == 0
    assert coordinator.snapshot()["gate_waiters"] == 0
    replacement = await asyncio.wait_for(coordinator.acquire(), timeout=1)
    await replacement.abandon()


async def test_cancelled_probe_abandon_finishes_state_transition():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
        )
    )
    failed = await coordinator.acquire()
    await failed.record_failure()
    probe = await asyncio.wait_for(coordinator.acquire(), timeout=1)
    probe.mark_ready()

    await coordinator._state_lock.acquire()
    abandon_task = asyncio.create_task(probe.abandon())
    await asyncio.sleep(0)
    abandon_task.cancel()
    coordinator._state_lock.release()

    with pytest.raises(asyncio.CancelledError):
        await abandon_task

    assert coordinator.snapshot()["half_open_probe_inflight"] is False
    replacement = await asyncio.wait_for(coordinator.acquire(), timeout=1)
    await replacement.abandon()


async def test_closed_installation_circuits_are_garbage_collected():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_concurrent_restarts=1,
            restart_failure_threshold=1,
        )
    )
    failed = await coordinator.acquire("installation-a")
    await failed.record_failure()
    probe = await asyncio.wait_for(coordinator.acquire("installation-a"), timeout=1)

    probe.mark_ready()
    await probe.mark_stable()

    assert coordinator.snapshot()["tracked_circuits"] == 0


async def test_expired_subthreshold_circuit_entries_are_garbage_collected():
    now = 100.0
    coordinator = PluginRestartCoordinator(clock=lambda: now)
    coordinator.configure(
        _policy(
            restart_failure_threshold=3,
            restart_failure_window_seconds=0.5,
            restart_circuit_open_seconds=10.0,
        )
    )

    failed = await coordinator.acquire("installation-a")
    await failed.record_failure()
    assert coordinator.snapshot()["tracked_circuits"] == 1

    now += 1.0

    assert coordinator.snapshot()["tracked_circuits"] == 0
    assert coordinator.snapshot()["failures_in_window"] == 0


async def test_restart_circuit_map_is_bounded_by_independent_control_limit():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(
        _policy(
            max_pending_registrations=2,
            restart_failure_threshold=3,
            restart_failure_window_seconds=60.0,
        )
    )

    for installation_uuid in ("installation-a", "installation-b"):
        permit = await coordinator.acquire(installation_uuid)
        await permit.record_failure()

    permit = await coordinator.acquire("installation-c")
    with pytest.raises(RuntimeError, match="circuit capacity"):
        await permit.record_failure()
    await permit.abandon()

    assert coordinator.snapshot()["tracked_circuits"] == 2


def test_restart_policy_is_immutable_after_configuration():
    coordinator = PluginRestartCoordinator()
    coordinator.configure(_policy())
    coordinator.configure(_policy())

    with pytest.raises(ValueError, match="cannot be changed"):
        coordinator.configure(_policy(restart_failure_threshold=3))
