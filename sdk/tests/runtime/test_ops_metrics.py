from __future__ import annotations

import builtins
import os

import pytest

from langbot_plugin.runtime import ops_metrics


def test_sample_process_resources_returns_empty_without_proc(monkeypatch):
    def _missing(*args, **kwargs):
        raise FileNotFoundError("no /proc")

    monkeypatch.setattr(builtins, "open", _missing)

    assert ops_metrics.sample_process_resources() == {}


def test_sample_process_resources_parses_proc_files(monkeypatch):
    # ``os.sysconf`` is POSIX-only; inject it so the /proc parser is exercised
    # on every development platform.
    monkeypatch.setattr(
        os,
        "sysconf",
        lambda name: {"SC_PAGE_SIZE": 4096, "SC_CLK_TCK": 100}[name],
        raising=False,
    )
    statm = "1024 250 100 1 0 200 0\n"
    # Fields after comm: state ppid pgrp session tty tpgid flags minflt cminflt
    # majflt cmajflt utime stime => utime=100, stime=50 at tail offsets 11/12.
    stat = (
        b"4242 (python worker) S 1 4242 4242 0 -1 4194560 1 0 0 0 100 50 0 0 20 0 1 0\n"
    )

    def _fake_open(path, *args, **kwargs):
        payload = statm if path == "/proc/self/statm" else stat
        text = payload.decode() if isinstance(payload, bytes) else payload

        class _Handle:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return payload

            def __iter__(self):
                return iter(text.splitlines(True))

        return _Handle()

    monkeypatch.setattr(builtins, "open", _fake_open)

    snapshot = ops_metrics.sample_process_resources()

    assert snapshot["pid"] > 0
    assert snapshot["rss_bytes"] > 0
    # 150 clock ticks at 100 Hz == 1.5 seconds.
    assert snapshot["cpu_seconds"] == pytest.approx(1.5)


def test_snapshot_exposes_only_aggregate_fields():
    metrics = ops_metrics.RuntimeOpsMetrics()

    snapshot = metrics.snapshot()

    assert snapshot["shared_worker_processes_started_total"] == 0
    assert snapshot["dependency_environment_prepare_seconds_last"] == 0.0
    assert snapshot["uptime_seconds"] >= 0.0
    assert all(isinstance(value, (int, float)) for value in snapshot.values()), snapshot


def test_backoff_helpers_track_current_and_total():
    metrics = ops_metrics.RuntimeOpsMetrics()

    metrics.record_shared_backoff(2.5)
    metrics.record_shared_backoff(1.5)
    metrics.record_dedicated_backoff(-3.0)

    assert metrics.shared_backoff_current_seconds == 1.5
    assert metrics.shared_backoff_total_seconds == 4.0
    assert metrics.dedicated_backoff_current_seconds == 0.0
    assert metrics.dedicated_backoff_total_seconds == 0.0

    metrics.clear_shared_backoff()
    metrics.clear_dedicated_backoff()

    assert metrics.shared_backoff_current_seconds == 0.0
