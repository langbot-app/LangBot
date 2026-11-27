import logging
from unittest import mock

import pytest

from langbot_plugin.box.identity import BoxIdentity
from langbot_plugin.box.runtime import BoxRuntime


def test_persistent_identity_survives_restart(tmp_path):
    first = BoxIdentity(logging.getLogger(), None, tmp_path)
    second = BoxIdentity(logging.getLogger(), None, tmp_path)
    other = BoxIdentity(logging.getLogger(), None, tmp_path / "other")
    assert first.instance_id == second.instance_id
    assert first.instance_id != other.instance_id


def test_explicit_identity_precedence(monkeypatch, tmp_path):
    BoxIdentity(logging.getLogger(), None, tmp_path)
    monkeypatch.setenv("LANGBOT_BOX_CONFIG", '{"instance_id":"config-id"}')
    assert (
        BoxRuntime(logging.getLogger(), backends=[], data_dir=tmp_path).instance_id
        == "config-id"
    )
    monkeypatch.setenv("LANGBOT_BOX_INSTANCE_ID", "env-id")
    assert (
        BoxRuntime(logging.getLogger(), backends=[], data_dir=tmp_path).instance_id
        == "env-id"
    )
    assert (
        BoxRuntime(
            logging.getLogger(), backends=[], instance_id="cli-id", data_dir=tmp_path
        ).instance_id
        == "cli-id"
    )


@pytest.mark.parametrize("instance_id", ["", "../bad", "a@b", "a/b", "a" * 129, "a b"])
def test_invalid_explicit_identity_is_rejected(instance_id, tmp_path):
    with pytest.raises(ValueError):
        BoxIdentity(logging.getLogger(), instance_id, tmp_path)


@pytest.mark.parametrize("instance_id", ["same-id", "core:instance"])
def test_same_identity_lock_refuses_concurrent_runtime_and_releases(
    tmp_path, instance_id
):
    first = BoxIdentity(logging.getLogger(), instance_id, tmp_path)
    second = BoxIdentity(logging.getLogger(), instance_id, tmp_path)
    other = BoxIdentity(logging.getLogger(), "other-id", tmp_path)
    try:
        assert first.acquire()
        assert other.acquire()
        with pytest.raises(RuntimeError, match="already in use"):
            second.acquire()
        first.release()
        assert second.acquire()
    finally:
        first.release()
        second.release()
        other.release()


def test_core_identity_and_backend_reselection_keep_same_owner(tmp_path):
    first_backend, second_backend = mock.Mock(), mock.Mock()
    runtime = BoxRuntime(
        logging.getLogger(),
        backends=[first_backend, second_backend],
        instance_id="instance_12345678-abcd",
        data_dir=tmp_path,
    )
    assert (
        first_backend.instance_id == second_backend.instance_id == runtime.instance_id
    )
    with pytest.raises(ValueError, match="fixed at startup"):
        runtime.init({"instance_id": "different-owner"})
    assert runtime.instance_id == "instance_12345678-abcd"


@pytest.mark.anyio
async def test_rpc_shutdown_keeps_identity_locked(tmp_path):
    runtime = BoxRuntime(
        logging.getLogger(), backends=[], instance_id="owner", data_dir=tmp_path
    )
    second = BoxIdentity(logging.getLogger(), "owner", tmp_path)
    assert runtime._identity.acquire()
    try:
        await runtime.shutdown(release_identity=False)
        with pytest.raises(RuntimeError, match="already in use"):
            second.acquire()
        await runtime.shutdown()
        assert second.acquire()
    finally:
        runtime._identity.release()
        second.release()


@pytest.mark.anyio
async def test_random_identity_fallback_never_cleans(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("LANGBOT_BOX_CONFIG", raising=False)
    unwritable = tmp_path / "file"
    unwritable.write_text("not a directory")
    backend = mock.Mock(name="selected")
    secondary = mock.Mock(name="secondary")
    secondary.name = "secondary"
    secondary.initialize = mock.AsyncMock()
    secondary.cleanup_orphaned_containers = mock.AsyncMock()
    backend.cleanup_orphaned_containers = mock.AsyncMock()
    runtime = BoxRuntime(
        logging.getLogger(), backends=[backend, secondary], data_dir=unwritable
    )
    with mock.patch.object(
        runtime, "_select_backend", mock.AsyncMock(return_value=backend)
    ):
        await runtime.initialize()
    try:
        assert not runtime._identity.persistent
        backend.cleanup_orphaned_containers.assert_not_awaited()
        assert await runtime._get_backend("secondary") is secondary
        secondary.initialize.assert_awaited_once()
        secondary.cleanup_orphaned_containers.assert_not_awaited()
        assert "without orphan cleanup" in caplog.text
    finally:
        await runtime.shutdown()
        await runtime.stop_background_reaper()


@pytest.mark.anyio
async def test_empty_identity_never_cleans_docker_or_nsjail(tmp_path):
    from langbot_plugin.box.backend import DockerBackend
    from langbot_plugin.box.nsjail_backend import NsjailBackend

    docker = DockerBackend(logging.getLogger())
    with mock.patch.object(docker, "_run_command", mock.AsyncMock()) as command:
        await docker.cleanup_orphaned_containers("")
    command.assert_not_awaited()
    nsjail = NsjailBackend(logging.getLogger())
    nsjail._base_dir = tmp_path
    (tmp_path / "legacy-session").mkdir()
    with mock.patch.object(nsjail, "_kill_orphaned_session_processes_sync") as kill:
        await nsjail.cleanup_orphaned_containers("")
    kill.assert_not_called()
    assert (tmp_path / "legacy-session").exists()
