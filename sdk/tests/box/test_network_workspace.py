"""Runtime-owned workspaces retain the existing execution and transfer fences."""

import asyncio
import json
import logging
from pathlib import Path
from unittest import mock

import pytest

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import (
    BoxAdmissionError,
    BoxCapacityExceededError,
    BoxError,
    BoxRuntimeUnavailableError,
    BoxSessionNotFoundError,
    BoxValidationError,
)
from langbot_plugin.box.host_backend import HostProcessBackend
from langbot_plugin.box.models import BoxArtifactMountSpec, BoxMountSpec, BoxSpec
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.tenancy import namespace_session_id
from langbot_plugin.entities.io.context import ActionContext

from .test_artifact_cache import publication  # noqa: F401
from .test_admission import _context, _grant, _runtime
from .test_runtime import FakeBackend


_CONTEXT = ActionContext(
    instance_uuid="network-instance",
    workspace_uuid="workspace-a",
    placement_generation=2,
)
_LOGGER = logging.getLogger(__name__)


def _spec(name="one", **kwargs):
    return BoxSpec(
        session_id=namespace_session_id(_CONTEXT, name), cmd="true", **kwargs
    )


@pytest.fixture
async def network_runtime(tmp_path, monkeypatch):
    root = tmp_path / "runtime-root"
    monkeypatch.setenv(
        "LANGBOT_BOX_CONFIG",
        json.dumps({"local": {"host_root": str(root), "default_workspace": "default"}}),
    )
    backend = FakeBackend(_LOGGER, name="docker")
    runtime = BoxRuntime(
        _LOGGER,
        backends=[backend],
        max_sessions=2,
        instance_id=_CONTEXT.instance_uuid,
        data_dir=tmp_path / "identity",
    )
    runtime.init({"backend": "docker", "file_transfer_mode": "network"})
    await runtime.initialize()
    try:
        yield runtime, backend
    finally:
        backend.stop_session.side_effect = backend._stop_session
        await runtime.stop_background_reaper()
        await runtime.event_loop_monitor.stop()
        await runtime.shutdown()


@pytest.mark.parametrize(
    "mode,ack,accepted",
    [
        ("legacy", {}, True),
        ("network", {}, False),
        ("network", {"network_workspace": False}, False),
        ("network", {"network_workspace": True}, True),
    ],
)
async def test_init_requires_explicit_network_ack(mode, ack, accepted):
    client = ActionRPCBoxClient(_LOGGER)
    client.set_handler(mock.Mock(call_action=mock.AsyncMock(return_value=ack)))
    if accepted:
        await client.init({"file_transfer_mode": mode})
    else:
        with pytest.raises(BoxRuntimeUnavailableError, match="updated Box Runtime"):
            await client.init({"file_transfer_mode": mode})


async def test_owned_workspace_reuse_transfer_storage_and_stop(
    network_runtime, tmp_path
):
    runtime, backend = network_runtime
    original = runtime._default_workspace()
    runtime.init(
        {
            "file_transfer_mode": "network",
            "local": {
                "host_root": str(tmp_path / "core"),
                "default_workspace": str(tmp_path / "core"),
                "allowed_mount_roots": ["/"],
            },
        }
    )
    assert runtime._default_workspace() == original
    assert runtime._allowed_mount_roots() != ["/"]
    legacy = Path(original, "tenants", "keep")
    legacy.mkdir(parents=True)
    (legacy / "data").write_text("legacy data")
    spec = _spec()
    public = await runtime.create_session(spec, _CONTEXT)
    assert public["host_path"] is None
    session = runtime._sessions[spec.session_id]
    workspace = Path(session.info.host_path)
    assert ".langbot-network-workspaces" in workspace.parts
    await runtime.upload_file(
        spec.session_id, "/workspace/draft.txt", b"draft", _CONTEXT
    )
    assert (
        await runtime.download_file(spec.session_id, "/workspace/draft.txt", _CONTEXT)
        == b"draft"
    )
    await runtime.create_session(spec, _CONTEXT)
    assert backend.started_sessions == 1
    report = await runtime.get_storage_analysis(_CONTEXT)
    assert any(
        d["kind"] == "root" and d["size_bytes"] == 5 for d in report["directories"]
    )
    await runtime.delete_session(spec.session_id)
    assert not workspace.exists()
    assert (legacy / "data").read_text() == "legacy data"


@pytest.mark.parametrize("field", ["host_path", "extra_mounts"])
async def test_network_rejects_host_mounts_before_allocating(
    network_runtime, tmp_path, field
):
    runtime, backend = network_runtime
    values = (
        {"host_path": str(tmp_path)}
        if field == "host_path"
        else {
            "extra_mounts": [
                BoxMountSpec(
                    host_path=str(tmp_path), mount_path="/workspace/extra", mode="ro"
                )
            ]
        }
    )
    with pytest.raises(BoxValidationError, match="not host paths"):
        await runtime.create_session(_spec(**values), _CONTEXT)
    assert not runtime._sessions
    assert backend.started_sessions == 0


async def test_uncertain_start_is_fenced_and_capacity_bounds_allocations(
    network_runtime,
):
    runtime, backend = network_runtime
    runtime.max_sessions = 1
    backend.start_session = mock.AsyncMock(
        side_effect=RuntimeError("uncertain startup")
    )
    spec = _spec()
    with pytest.raises(RuntimeError, match="uncertain startup"):
        await runtime.create_session(spec, _CONTEXT)
    owner, _ = runtime._failed_start_workspaces[spec.session_id]
    assert Path(owner[0]).is_dir()
    with pytest.raises(BoxError, match="fenced"):
        await runtime.create_session(spec, _CONTEXT)
    with pytest.raises(BoxCapacityExceededError):
        await runtime.create_session(_spec("other"), _CONTEXT)
    assert len(list(Path(owner[0]).parent.iterdir())) == 1
    assert (await runtime.get_capacity(_CONTEXT))["remaining"] == 0
    backend.start_session.assert_awaited_once()


async def test_cancelled_start_waits_for_creation_then_retires_owned_workspace(
    network_runtime,
):
    runtime, backend = network_runtime
    started, release = asyncio.Event(), asyncio.Event()
    original = backend.start_session
    paths = []

    async def slow_start(spec):
        paths.append(Path(spec.host_path))
        started.set()
        await release.wait()
        return await original(spec)

    backend.start_session = slow_start
    task = asyncio.create_task(runtime.create_session(_spec(), _CONTEXT))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert not runtime._sessions and not runtime._failed_start_workspaces
    assert not paths[0].exists()
    backend.stop_session.assert_awaited_once()


@pytest.mark.parametrize(
    "scenario",
    [
        "root",
        "child",
        "no_ref",
        "other",
        "escape",
        "missing",
        "non_normal",
        "backslash",
    ],
)
async def test_managed_network_workdir_requires_a_prepared_scoped_artifact(
    tmp_path,
    publication,
    scenario,  # noqa: F811
):
    runtime, backend = _runtime(tmp_path)
    runtime.init({"file_transfer_mode": "network"})
    await runtime.initialize()
    context = _context()
    try:
        await runtime.upsert_sandbox_admission_grant(_grant(context))
        descriptor, content, _ = publication()
        await runtime.prepare_artifact(descriptor, content, context)
        mount = BoxArtifactMountSpec(content_digest=descriptor.content_digest)
        unprepared = BoxArtifactMountSpec(content_digest="sha256:" + "0" * 64)
        workdir = mount.mount_path
        references = [mount]
        if scenario == "child":
            workdir += "/scripts"
        elif scenario == "no_ref":
            references = []
        elif scenario == "other":
            workdir = unprepared.mount_path
        elif scenario == "escape":
            workdir += "/../elsewhere"
        elif scenario == "missing":
            workdir, references = unprepared.mount_path, [unprepared]
        elif scenario == "non_normal":
            workdir += "//scripts"
        elif scenario == "backslash":
            workdir += "/bad\\name"
        spec = BoxSpec(
            session_id="global", cmd="true", workdir=workdir, artifact_mounts=references
        )
        if scenario in {"root", "child"}:
            assert (await runtime.execute(spec, context)).ok
            assert backend.exec_calls == 1
        elif scenario == "missing":
            with pytest.raises(ValueError, match="not prepared"):
                await runtime.execute(spec, context)
            assert backend.started_specs == []
        else:
            with pytest.raises(BoxAdmissionError, match="workdir"):
                await runtime.execute(spec, context)
            assert backend.started_specs == []
    finally:
        await runtime.stop_background_reaper()
        await runtime.event_loop_monitor.stop()
        await runtime.shutdown()


@pytest.mark.parametrize("stop_fails", [False, True])
async def test_cancelled_execution_only_removes_workspace_after_stop(
    network_runtime, stop_fails
):
    runtime, backend = network_runtime
    spec = _spec()
    await runtime.create_session(spec, _CONTEXT)
    workspace = Path(runtime._sessions[spec.session_id].info.host_path)
    started = asyncio.Event()

    async def blocked_exec(session, spec):
        started.set()
        await asyncio.Event().wait()

    backend.exec = blocked_exec
    if stop_fails:
        backend.stop_session.side_effect = RuntimeError("still running")
    task = asyncio.create_task(runtime.execute(spec, _CONTEXT))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert workspace.exists() is stop_fails
    if stop_fails:
        assert runtime._sessions[spec.session_id].closing
        backend.stop_session.side_effect = backend._stop_session
        await runtime.delete_session(spec.session_id)
        assert not workspace.exists()


@pytest.mark.parametrize("bound", ["bytes", "entries"])
async def test_runtime_enforces_quota_on_its_own_workspace(network_runtime, bound):
    runtime, backend = network_runtime
    spec = _spec(workspace_quota_mb=1)
    await runtime.create_session(spec, _CONTEXT)
    workspace = Path(runtime._sessions[spec.session_id].info.host_path)
    original = backend.exec
    runtime.max_workspace_entries = 2

    async def fill_workspace(session, spec):
        if bound == "bytes":
            (workspace / "large").write_bytes(b"x" * (1024 * 1024 + 1))
        else:
            for index in range(3):
                (workspace / str(index)).touch()
        return await original(session, spec)

    backend.exec = fill_workspace
    with pytest.raises(
        BoxValidationError, match="workspace (quota|entry limit) exceeded"
    ):
        await runtime.execute(spec, _CONTEXT)
    assert not workspace.exists()
    assert spec.session_id not in runtime._sessions


async def test_run_cleanup_uses_real_sandbox_and_cannot_resurrect_deleted_session(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("LANGBOT_BOX_CONFIG", raising=False)
    backend = HostProcessBackend(_LOGGER)
    runtime = BoxRuntime(
        _LOGGER,
        backends=[backend],
        instance_id=_CONTEXT.instance_uuid,
        data_dir=tmp_path / "identity",
    )
    runtime.init({"backend": "host", "file_transfer_mode": "network"})
    spec = _spec()
    await runtime.create_session(spec, _CONTEXT)
    workspace = Path(runtime._sessions[spec.session_id].info.host_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("keep")
    try:
        for directory in ("inbox", "outbox", ".langbot-snapshots"):
            (workspace / directory / "current").mkdir(parents=True)
            (workspace / directory / "current" / "payload").write_text("remove")
            (workspace / directory / "other").mkdir()
        (workspace / "draft").mkdir()
        await runtime.cleanup_run_files(spec.session_id, "current", _CONTEXT)
        assert (workspace / "draft").is_dir()
        for directory in ("inbox", "outbox", ".langbot-snapshots"):
            assert not (workspace / directory / "current").exists()
            assert (workspace / directory / "other").is_dir()
        (workspace / "inbox" / "current").symlink_to(outside, target_is_directory=True)
        await runtime.cleanup_run_files(spec.session_id, "current", _CONTEXT)
        assert (outside / "keep").read_text() == "keep"
        with pytest.raises(ValueError):
            await runtime.cleanup_run_files(spec.session_id, "../draft", _CONTEXT)
        await runtime.delete_session(spec.session_id)
        with pytest.raises(BoxSessionNotFoundError):
            await runtime.cleanup_run_files(spec.session_id, "current", _CONTEXT)
        assert not runtime._sessions
    finally:
        await runtime.shutdown()


async def test_cancelled_execution_releases_artifact_pins_after_backend_stop(
    network_runtime,
    publication,  # noqa: F811
):
    runtime, backend = network_runtime
    descriptor, content, _ = publication()
    await runtime.prepare_artifact(descriptor, content, _CONTEXT)
    cache = runtime.artifact_cache
    cache.idle_ttl_sec = 0
    started = asyncio.Event()

    async def blocked_exec(session, spec):
        started.set()
        await asyncio.Event().wait()

    backend.exec = blocked_exec
    spec = _spec(
        artifact_mounts=[BoxArtifactMountSpec(content_digest=descriptor.content_digest)]
    )
    task = asyncio.create_task(runtime.execute(spec, _CONTEXT))
    await asyncio.wait_for(started.wait(), 2)
    await runtime.reap_artifact_cache()
    assert cache.probe(_CONTEXT, descriptor)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await runtime.reap_artifact_cache()
    assert not cache.probe(_CONTEXT, descriptor)
    backend.stop_session.assert_awaited_once()
