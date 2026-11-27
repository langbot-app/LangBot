"""Docker/Podman bind sources must use the configured daemon-visible root."""

import logging
from pathlib import Path
from unittest import mock

import pytest

from langbot_plugin.box.backend import CLISandboxBackend, _CommandResult
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.models import ARTIFACT_MOUNT_ROOT, BoxSpec
from langbot_plugin.box.runtime import BoxRuntime


def configured_backend(tmp_path, monkeypatch, name):
    monkeypatch.delenv("LANGBOT_BOX_CONFIG", raising=False)
    logger = logging.getLogger(__name__)
    backend = CLISandboxBackend(logger, name, name)
    runtime = BoxRuntime(logger, backends=[backend])
    # Relative host roots use the runtime's working directory, not the workspace.
    monkeypatch.chdir(tmp_path)
    runtime.init({"local": {"host_root": "shared", "default_workspace": "default"}})
    return backend


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["docker", "podman"])
@pytest.mark.parametrize("mode", ["rw", "ro", "none"])
async def test_cache_mount_uses_shared_root_without_packages(
    tmp_path, monkeypatch, name, mode
):
    backend = configured_backend(tmp_path, monkeypatch, name)
    private_tmp = tmp_path / "container-private-tmp"
    private_tmp.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(private_tmp))
    workspace = tmp_path / "shared" / "default"
    command = mock.AsyncMock(return_value=_CommandResult(0, "", ""))
    with mock.patch.object(backend, "_run_command", command):
        first = await backend.start_session(
            BoxSpec(session_id="first", host_path=str(workspace), host_path_mode=mode)
        )
        second = await backend.start_session(BoxSpec(session_id="second"))
        roots = [Path(root) for root in backend._artifact_roots.values()]
        assert len(set(roots)) == 2
        assert all(
            root.parent == tmp_path / "shared" and root.is_dir() for root in roots
        )
        assert not list(private_tmp.iterdir())
        assert not list(workspace.iterdir())
        for call, root in zip(command.call_args_list, roots):
            args = call.args[0]
            assert f"{root}:{ARTIFACT_MOUNT_ROOT}:ro" in args
        await backend.stop_session(first)
        assert not roots[0].exists() and roots[1].is_dir()
        await backend.stop_session(second)
    assert not backend._artifact_roots
    assert not any(root.exists() for root in roots)


@pytest.mark.asyncio
async def test_failed_creation_cleans_shared_cache(tmp_path, monkeypatch):
    backend = configured_backend(tmp_path, monkeypatch, "docker")
    roots = []

    async def run(args, **kwargs):
        if args[1] == "run":
            roots.extend(Path(root) for root in backend._artifact_roots.values())
            assert roots[0].is_dir()
            raise BoxError("creation failed")
        return _CommandResult(0, "", "")

    with mock.patch.object(backend, "_run_command", side_effect=run):
        with pytest.raises(BoxError, match="creation failed"):
            await backend.start_session(BoxSpec(session_id="failed"))
    assert roots and not any(root.exists() for root in roots)
    assert not backend._artifact_roots


@pytest.mark.asyncio
async def test_unusable_shared_root_does_not_retry_in_private_tmp(
    tmp_path, monkeypatch
):
    backend = configured_backend(tmp_path, monkeypatch, "docker")
    backend.artifact_cache_parent = str(tmp_path / "file")
    Path(backend.artifact_cache_parent).write_text("not a directory")
    command = mock.AsyncMock()
    with mock.patch.object(backend, "_run_command", command):
        with pytest.raises(FileExistsError):
            await backend.start_session(BoxSpec(session_id="invalid"))
    command.assert_not_called()
    assert not backend._artifact_roots
