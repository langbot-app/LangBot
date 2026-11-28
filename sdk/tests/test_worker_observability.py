from types import SimpleNamespace

from langbot_plugin.runtime.plugin.worker_observability import worker_snapshot


def test_snapshot_includes_shared_and_dedicated_but_not_duplicate_slots():
    handler = SimpleNamespace(
        seq_id_index=98124,
        requests_total=12,
        resp_waiters={1: None},
        resp_queues={},
        stdio_process=None,
    )
    shared = SimpleNamespace(
        plugin_handler=handler,
        slots={1: None, 2: None},
        draining=False,
        registration_generation=3,
    )
    dedicated = SimpleNamespace(
        plugin_handler=handler, shared_worker=None, enabled=True, state="running"
    )
    slot = SimpleNamespace(shared_worker=shared)
    mgr = SimpleNamespace(
        _shared_workers={"abc": shared}, _installations={"a": dedicated, "b": slot}
    )
    rows = worker_snapshot(mgr)
    assert len(rows) == 2
    assert {r["mode"] for r in rows} == {"shared", "dedicated"}
    assert sorted(r["slots"] for r in rows) == [1, 2]
    assert all(r["requests_total"] == 12 for r in rows)
    assert all(r["inflight"] == 1 for r in rows)
    assert all("abc" not in r["worker_id"] for r in rows)


def test_missing_handler_is_not_reported_healthy():
    mgr = SimpleNamespace(
        _shared_workers={},
        _installations={
            "a": SimpleNamespace(
                plugin_handler=None, shared_worker=None, enabled=True, state="starting"
            )
        },
    )
    assert worker_snapshot(mgr)[0]["state"] == "starting"
    assert worker_snapshot(mgr)[0]["requests_total"] is None
