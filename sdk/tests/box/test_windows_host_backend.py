import asyncio
import io
import logging
import os
import shutil
import subprocess
import zipfile
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box import host_backend
from langbot_plugin.box import file_io
from langbot_plugin.box.errors import BoxValidationError
from langbot_plugin.box.models import BoxSpec


def test_shell_selection(monkeypatch, tmp_path):
    monkeypatch.setattr(host_backend, "_WINDOWS", True)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(
        shutil, "which", lambda name: name if name == "powershell.exe" else None
    )
    select = host_backend.HostProcessBackend._select_shell
    assert select() == ("powershell.exe", "powershell")
    bash = tmp_path / "Git/bin/bash.exe"
    bash.parent.mkdir(parents=True)
    bash.touch()
    assert select() == (str(bash), "git-bash")


@pytest.mark.skipif(os.name != "nt", reason="requires Windows host and junctions")
@pytest.mark.asyncio
async def test_network_file_round_trip(tmp_path):
    workspace = tmp_path / "workspace with spaces"
    backend = host_backend.HostProcessBackend(logging.getLogger(__name__))
    spec = BoxSpec(
        session_id="round-trip",
        host_path=str(workspace),
        cmd="cat /workspace/inbox/run/msg.txt",
        read_only_rootfs=False,
    )
    session = await backend.start_session(spec)
    info = workspace.stat()
    owner = str(workspace), info.st_dev, info.st_ino
    try:
        path = "/workspace/inbox/run/msg.txt"
        await backend.upload_file(session, path, b"hello", 10)
        result = await backend.exec(session, spec)
        assert result.exit_code == 0 and result.stdout == "hello", result.stderr
        assert await backend.download_file(session, path, 10) == b"hello"
        data = await backend.download_directory(session, "/workspace/inbox", 1024)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.read("run/msg.txt") == b"hello"
        assert file_io.workspace_usage(str(workspace), 10, 10) == (5, 3, False)
        assert file_io.run_files_present(owner, "run")
        junction = workspace / "junction"
        outside = tmp_path / "outside"
        outside.mkdir()
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)], check=True
        )
        try:
            with pytest.raises(ValueError, match="reparse"):
                await backend.upload_file(
                    session, "/workspace/junction/msg.txt", b"no", 10
                )
            assert not (outside / "msg.txt").exists()
        finally:
            junction.rmdir()
    finally:
        await backend.stop_session(session)
        await backend.remove_owned_workspace(session, owner)
    assert not workspace.exists()


@pytest.mark.asyncio
async def test_windows_terminates_job_before_waiting():
    job = Mock()
    process = AsyncMock()
    await host_backend.HostProcessBackend._terminate_process_group(process, job=job)
    job.terminate.assert_called_once_with()
    process.wait.assert_awaited_once_with()


@pytest.mark.skipif(os.name != "nt", reason="requires actual Windows shells")
@pytest.mark.asyncio
@pytest.mark.parametrize("shell", ["git-bash", "powershell"])
async def test_windows_exec(tmp_path, shell):
    backend = host_backend.HostProcessBackend(logging.getLogger(__name__))
    if shell == "powershell":
        backend._shell, backend._shell_kind = shutil.which("powershell.exe"), shell
    assert (await backend.get_readiness())["shell"] == shell
    workspace = tmp_path / "box workspace"
    command = (
        "echo hi && pwd && printf workspace-ok > /workspace/result.txt && cat /workspace/result.txt"
        if shell == "git-bash"
        else "Write-Output hi; Set-Content /workspace/result.txt workspace-ok; Get-Content /workspace/result.txt"
    )
    spec = BoxSpec(
        session_id="windows-host",
        host_path=str(workspace),
        cmd=command,
        read_only_rootfs=False,
    )
    session = await backend.start_session(spec)
    try:
        result = await asyncio.wait_for(backend.exec(session, spec), 30)
        assert result.exit_code == 0, result.stderr
        assert result.stdout.splitlines()[0] == "hi"
        assert result.stdout.splitlines()[-1] == "workspace-ok"
        assert (workspace / "result.txt").read_text().strip() == "workspace-ok"
        print(f"{shell}: {result.stdout.strip()}")
        state = backend._require_session(session)
        with pytest.raises(BoxValidationError, match="escapes"):
            backend._map_path(state, r"/workspace\..\outside")
        if shell == "powershell":
            with pytest.raises(BoxValidationError, match="require Git Bash"):
                await backend.exec(
                    session,
                    spec.model_copy(update={"cmd": "python3 - <<'PY'\nprint(1)\nPY"}),
                )
    finally:
        await backend.stop_session(session)
