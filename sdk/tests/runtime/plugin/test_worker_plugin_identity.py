from types import SimpleNamespace

from langbot_plugin.runtime.plugin.worker_observability import worker_snapshot


def test_worker_plugin_identity_for_both_modes():
    artifact = SimpleNamespace(
        plugin_author="alice", plugin_name="demo", plugin_version="1.2.3"
    )
    shared = SimpleNamespace(artifact=artifact, slots={})
    dedicated = SimpleNamespace(artifact=artifact, shared_worker=None)
    rows = worker_snapshot(
        SimpleNamespace(
            _shared_workers={"digest": shared}, _installations={"binding": dedicated}
        )
    )
    assert len(rows) == 2
    for row in rows:
        assert row["plugin_author"] == "alice"
        assert row["plugin_name"] == "demo"
        assert row["plugin_version"] == "1.2.3"
        assert "binding" not in str(row)
