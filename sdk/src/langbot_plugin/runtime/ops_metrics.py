from __future__ import annotations

import os
import time
from typing import Any


def sample_process_resources() -> dict[str, int | float]:
    """Return this process' pid, RSS and CPU time, or ``{}`` off Linux.

    ``/proc`` is read on demand: the probe endpoint is polled by the Cloud ops
    dashboard and by the soak gate, so sampling stays out of the hot path and no
    background task is added.
    """

    if not hasattr(os, "sysconf"):
        return {}

    try:
        with open("/proc/self/statm", "r", encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError):
        return {}

    snapshot: dict[str, int | float] = {
        "pid": os.getpid(),
        "rss_bytes": resident_pages * page_size,
    }
    try:
        with open("/proc/self/stat", "rb") as handle:
            raw = handle.read()
        # ``comm`` may contain spaces and parentheses, so only the fields after
        # the final ')' are positional: utime/stime are fields 14 and 15.
        tail = raw[raw.rindex(b")") + 2 :].split()
        clock_ticks = int(os.sysconf("SC_CLK_TCK"))
        snapshot["cpu_seconds"] = (int(tail[11]) + int(tail[12])) / clock_ticks
    except (OSError, ValueError, IndexError):
        pass
    return snapshot


class RuntimeOpsMetrics:
    """Process-lifetime counters for the Cloud Plugin Runtime ops dashboard.

    Every value is an aggregate over the whole Runtime process. No
    installation UUID, Workspace UUID, plugin identity or artifact digest is
    ever recorded here, which keeps the payload safe for the unauthenticated
    ``/healthz`` probe that the Cloud ops dashboard and the soak gate poll.

    Counters are incremented on lifecycle paths that already exist; nothing in
    this module starts a task, timer, or background sampler.
    """

    __slots__ = (
        "started_at",
        "shared_processes_started_total",
        "shared_registrations_total",
        "shared_launch_failures_total",
        "shared_transport_timeouts_total",
        "shared_capacity_rejections_total",
        "shared_stops_total",
        "shared_slot_attach_total",
        "shared_slot_attach_success_total",
        "shared_slot_attach_failures_total",
        "shared_slot_attach_timeouts_total",
        "shared_slot_detach_total",
        "shared_backoff_current_seconds",
        "shared_backoff_total_seconds",
        "dedicated_backoff_current_seconds",
        "dedicated_backoff_total_seconds",
        "dependency_cache_hits_total",
        "dependency_cache_misses_total",
        "dependency_prepare_failures_total",
        "dependency_prepare_seconds_total",
        "dependency_prepare_seconds_last",
    )

    def __init__(self) -> None:
        self.started_at = time.monotonic()
        self.shared_processes_started_total = 0
        self.shared_registrations_total = 0
        self.shared_launch_failures_total = 0
        self.shared_transport_timeouts_total = 0
        self.shared_capacity_rejections_total = 0
        self.shared_stops_total = 0
        self.shared_slot_attach_total = 0
        self.shared_slot_attach_success_total = 0
        self.shared_slot_attach_failures_total = 0
        self.shared_slot_attach_timeouts_total = 0
        self.shared_slot_detach_total = 0
        self.shared_backoff_current_seconds = 0.0
        self.shared_backoff_total_seconds = 0.0
        self.dedicated_backoff_current_seconds = 0.0
        self.dedicated_backoff_total_seconds = 0.0
        self.dependency_cache_hits_total = 0
        self.dependency_cache_misses_total = 0
        self.dependency_prepare_failures_total = 0
        self.dependency_prepare_seconds_total = 0.0
        self.dependency_prepare_seconds_last = 0.0

    @property
    def uptime_seconds(self) -> float:
        return max(time.monotonic() - self.started_at, 0.0)

    def record_shared_backoff(self, delay_seconds: float) -> None:
        """Record one shared-worker restart delay before it is slept off."""

        delay = max(float(delay_seconds), 0.0)
        self.shared_backoff_current_seconds = delay
        self.shared_backoff_total_seconds += delay

    def record_dedicated_backoff(self, delay_seconds: float) -> None:
        """Record one dedicated-worker restart delay before it is slept off."""

        delay = max(float(delay_seconds), 0.0)
        self.dedicated_backoff_current_seconds = delay
        self.dedicated_backoff_total_seconds += delay

    def clear_shared_backoff(self) -> None:
        self.shared_backoff_current_seconds = 0.0

    def clear_dedicated_backoff(self) -> None:
        self.dedicated_backoff_current_seconds = 0.0

    def snapshot(self) -> dict[str, Any]:
        """Return identity-free counters and gauges."""

        return {
            "started_at_monotonic": self.started_at,
            "uptime_seconds": self.uptime_seconds,
            "shared_worker_processes_started_total": (
                self.shared_processes_started_total
            ),
            "shared_worker_registrations_total": self.shared_registrations_total,
            "shared_worker_launch_failures_total": self.shared_launch_failures_total,
            "shared_worker_transport_timeouts_total": (
                self.shared_transport_timeouts_total
            ),
            "shared_worker_capacity_rejections_total": (
                self.shared_capacity_rejections_total
            ),
            "shared_worker_stops_total": self.shared_stops_total,
            "shared_slot_attach_total": self.shared_slot_attach_total,
            "shared_slot_attach_success_total": self.shared_slot_attach_success_total,
            "shared_slot_attach_failures_total": (
                self.shared_slot_attach_failures_total
            ),
            "shared_slot_attach_timeouts_total": (
                self.shared_slot_attach_timeouts_total
            ),
            "shared_slot_detach_total": self.shared_slot_detach_total,
            "shared_backoff_current_seconds": self.shared_backoff_current_seconds,
            "shared_backoff_total_seconds": self.shared_backoff_total_seconds,
            "dedicated_backoff_current_seconds": self.dedicated_backoff_current_seconds,
            "dedicated_backoff_total_seconds": self.dedicated_backoff_total_seconds,
            "dependency_environment_cache_hits_total": (
                self.dependency_cache_hits_total
            ),
            "dependency_environment_cache_misses_total": (
                self.dependency_cache_misses_total
            ),
            "dependency_environment_prepare_failures_total": (
                self.dependency_prepare_failures_total
            ),
            "dependency_environment_prepare_seconds_total": (
                self.dependency_prepare_seconds_total
            ),
            "dependency_environment_prepare_seconds_last": (
                self.dependency_prepare_seconds_last
            ),
        }
