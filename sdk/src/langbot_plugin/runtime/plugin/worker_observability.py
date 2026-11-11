"""Identity-free per-worker telemetry for the existing health reporting path."""

import hashlib
import time


def worker_snapshot(manager):
    rows = []
    shared = getattr(manager, "_shared_workers", {})
    workers = [("shared", key, value) for key, value in shared.items()]
    workers += [
        ("dedicated", str(key), value)
        for key, value in getattr(manager, "_installations", {}).items()
        if getattr(value, "shared_worker", None) is None
    ]
    for mode, key, worker in workers:
        handler = getattr(worker, "plugin_handler", None)
        monitor = getattr(worker, "watchdog", None)
        process = getattr(handler, "stdio_process", None)
        state = getattr(
            worker, "state", "running" if handler is not None else "starting"
        )
        if getattr(worker, "draining", False):
            state = "draining"
        if (
            handler is not None
            and monitor is not None
            and monitor.failed_since is not None
        ):
            state = "unresponsive"
        rows.append(
            {
                "worker_id": hashlib.sha256(f"{mode}:{key}".encode()).hexdigest()[:24],
                "plugin_author": getattr(
                    getattr(worker, "artifact", None), "plugin_author", None
                ),
                "plugin_name": getattr(
                    getattr(worker, "artifact", None), "plugin_name", None
                ),
                "plugin_version": getattr(
                    getattr(worker, "artifact", None), "plugin_version", None
                ),
                "mode": mode,
                "state": state,
                "slots": len(worker.slots) if mode == "shared" else 1,
                "requests_total": getattr(handler, "requests_total", None),
                "inflight": len(getattr(handler, "resp_waiters", {}))
                + len(getattr(handler, "resp_queues", {})),
                "pid": getattr(process, "pid", None),
                "generation": getattr(worker, "registration_generation", None),
                "watchdog_restarts": getattr(worker, "watchdog_restarts", 0),
                "last_watchdog_restart_at": getattr(
                    worker, "last_watchdog_restart_at", None
                ),
                "probe_failures": monitor.failures if monitor else 0,
                "last_response_age_seconds": max(
                    0, time.monotonic() - monitor.last_success
                )
                if monitor and monitor.last_success is not None
                else None,
            }
        )
    return rows
