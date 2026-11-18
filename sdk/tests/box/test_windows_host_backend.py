import asyncio
import json
import logging
import os
import shutil
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box import host_backend
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


@pytest.mark.skipif(os.name != "nt", reason="requires actual Windows shells")
@pytest.mark.asyncio
async def test_windows_git_bash_native_file_tool_shape(tmp_path):
    """Mirror Core's native file-tool wrapper: python3 lookup + quoted heredoc."""
    backend = host_backend.HostProcessBackend(logging.getLogger(__name__))
    if backend._shell_kind != "git-bash":
        pytest.skip("Git Bash is not installed")
    workspace = tmp_path / "box workspace"
    script = (
        "import json, os\n"
        'path = "/workspace/sub dir/a.txt"\n'
        "if not path.startswith('/workspace'):\n"
        "    print(json.dumps({'ok': False}))\n"
        "else:\n"
        "    os.makedirs(os.path.dirname(path), exist_ok=True)\n"
        "    with open(path, 'w', encoding='utf-8') as f:\n"
        '        f.write("it\'s $HOME `x`")\n'
        "    with open(path, encoding='utf-8') as f:\n"
        "        print(json.dumps({'ok': True, 'content': f.read()}))"
    )
    command = (
        "PYTHON_BIN=$(command -v python3 || true); "
        'if [ -z "$PYTHON_BIN" ]; then echo no-python; exit 0; fi; '
        f"\"$PYTHON_BIN\" - <<'PY'\n{script}\nPY"
    )
    spec = BoxSpec(
        session_id="windows-host-file-tool",
        host_path=str(workspace),
        cmd=command,
        read_only_rootfs=False,
    )
    session = await backend.start_session(spec)
    try:
        result = await asyncio.wait_for(backend.exec(session, spec), 30)
        assert result.exit_code == 0, result.stderr
        print(f"file-tool: {result.stdout.strip()}")
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload == {"ok": True, "content": "it's $HOME `x`"}
        assert (workspace / "sub dir" / "a.txt").read_text(
            encoding="utf-8"
        ) == "it's $HOME `x`"
    finally:
        await backend.stop_session(session)
