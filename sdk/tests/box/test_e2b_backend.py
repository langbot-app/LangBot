"""Unit tests for E2BSandboxBackend.

These tests do NOT require e2b package to be installed – they mock the E2B SDK
to verify parameter mapping, session lifecycle, and availability detection.
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest import mock

import pytest

from langbot_plugin.box.e2b_backend import (
    E2BSandboxBackend,
    _adapt_path_for_e2b,
    _build_e2b_host_manifest,
    _check_e2b_available,
    _rewrite_command_paths_for_e2b,
)
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.models import (
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxMountSpec,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)


@pytest.fixture
def logger():
    return logging.getLogger("test.e2b")


@pytest.fixture
def backend(logger):
    b = E2BSandboxBackend(logger=logger)
    b.instance_id = "test123"
    return b


@pytest.fixture
def mock_e2b_module():
    """Mock the e2b module for tests."""
    mock_async_sandbox = mock.MagicMock()
    mock_async_sandbox.sandbox_id = "sandbox-test-123"

    # Mock AsyncSandbox.create
    mock_async_sandbox.create = mock.AsyncMock(return_value=mock_async_sandbox)

    # Mock AsyncSandbox.connect
    mock_async_sandbox.connect = mock.AsyncMock(return_value=mock_async_sandbox)

    # Mock AsyncSandbox.kill
    mock_async_sandbox.kill = mock.AsyncMock(return_value=True)

    # Mock commands.run result
    mock_command_result = mock.MagicMock()
    mock_command_result.stdout = "output"
    mock_command_result.stderr = ""
    mock_command_result.exit_code = 0

    mock_commands = mock.MagicMock()
    mock_commands.run = mock.AsyncMock(return_value=mock_command_result)
    mock_async_sandbox.commands = mock_commands

    # Mock the module import
    with (
        mock.patch("langbot_plugin.box.e2b_backend._e2b_available", None),
        mock.patch("langbot_plugin.box.e2b_backend._AsyncSandbox", None),
        mock.patch("langbot_plugin.box.e2b_backend._CommandResult", None),
    ):
        # Simulate successful import
        import langbot_plugin.box.e2b_backend as e2b_backend

        e2b_backend._e2b_available = True
        e2b_backend._AsyncSandbox = mock_async_sandbox
        yield mock_async_sandbox


# ── Path adaptation ────────────────────────────────────────────────────


def test_adapt_path_workspace():
    """_adapt_path_for_e2b maps /workspace to /home/user/workspace."""
    assert _adapt_path_for_e2b("/workspace") == "/home/user/workspace"
    assert _adapt_path_for_e2b("/workspace/subdir") == "/home/user/workspace/subdir"


def test_adapt_path_other_paths_unchanged():
    """_adapt_path_for_e2b doesn't modify paths not starting with /workspace."""
    assert _adapt_path_for_e2b("/home/user") == "/home/user"
    assert _adapt_path_for_e2b("/tmp") == "/tmp"
    assert _adapt_path_for_e2b("/code") == "/code"


def test_extra_mount_projections_are_excluded_from_workspace_sync(backend):
    spec = BoxSpec(
        session_id="overlay",
        extra_mounts=[
            BoxMountSpec(
                host_path="/tmp/revision",
                mount_path="/workspace/.skills/demo",
                mode=BoxHostMountMode.READ_ONLY,
            )
        ],
    )

    shadowed = backend._main_mount_shadow_paths(spec)

    assert shadowed == {".skills/demo"}
    assert backend._path_is_shadowed(".skills/demo/run.py", shadowed) is True
    assert backend._path_is_shadowed("notes.txt", shadowed) is False


def test_rewrite_command_paths_for_e2b_respects_path_boundaries():
    command = (
        "ls /workspace && echo /workspace/a && echo /workspaces && echo x/workspace"
    )

    rewritten = _rewrite_command_paths_for_e2b(command)

    assert rewritten == (
        "ls /home/user/workspace && echo /home/user/workspace/a "
        "&& echo /workspaces && echo x/workspace"
    )


# ── is_available ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_is_available_no_package(backend):
    """is_available returns False when e2b package is not installed."""
    with mock.patch(
        "langbot_plugin.box.e2b_backend._check_e2b_available", return_value=False
    ):
        assert await backend.is_available() is False


@pytest.mark.anyio
async def test_is_available_no_api_key(backend):
    """is_available returns False when E2B_API_KEY is not set."""
    backend._api_key = None
    with mock.patch(
        "langbot_plugin.box.e2b_backend._check_e2b_available", return_value=True
    ):
        assert await backend.is_available() is False


@pytest.mark.anyio
async def test_is_available_with_api_key(backend):
    """is_available returns True when both package and API key are available."""
    backend._api_key = "test-api-key"
    with mock.patch(
        "langbot_plugin.box.e2b_backend._check_e2b_available", return_value=True
    ):
        assert await backend.is_available() is True


@pytest.mark.anyio
async def test_configure_from_langbot(backend, mock_e2b_module):
    """configure() applies settings from LangBot config.yaml."""
    backend.configure(
        {
            "api_key": "config-api-key",
            "api_url": "http://127.0.0.1:3000",
            "template": "python-3.11",
        }
    )
    await backend.initialize()

    # Environment variable takes precedence, so if not set, use config
    assert backend._api_key == "config-api-key"
    assert backend._api_url == "http://127.0.0.1:3000"
    assert backend._template == "python-3.11"


@pytest.mark.anyio
async def test_env_vars_override_config(backend, mock_e2b_module):
    """Environment variables take precedence over config.yaml values."""
    with mock.patch.dict(
        "os.environ", {"E2B_API_KEY": "env-api-key", "E2B_API_URL": "http://env-url"}
    ):
        backend.configure(
            {
                "api_key": "config-api-key",
                "api_url": "http://config-url",
            }
        )
        await backend.initialize()

        # Environment variables should win
        assert backend._api_key == "env-api-key"
        assert backend._api_url == "http://env-url"


# ── start_session ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_session_basic(backend, mock_e2b_module):
    """start_session creates sandbox with default parameters."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(session_id="sess1", cmd="echo hi")

    info = await backend.start_session(spec)

    assert info.backend_name == "e2b"
    assert info.session_id == "sess1"
    assert info.backend_session_id == "sandbox-test-123"
    # Session metadata keeps LangBot's logical mount path so later specs
    # with /workspace can reuse the same session.
    assert info.mount_path == "/workspace"

    # Verify AsyncSandbox.create was called with api_key
    mock_e2b_module.create.assert_called_once()
    call_kwargs = mock_e2b_module.create.call_args.kwargs
    assert call_kwargs.get("api_key") == "test-api-key"


@pytest.mark.anyio
async def test_is_session_alive_probes_remote_sandbox(backend, mock_e2b_module):
    backend._api_key = "test-api-key"
    info = await backend.start_session(BoxSpec(session_id="alive", cmd="true"))

    assert await backend.is_session_alive(info) is True
    mock_e2b_module.connect.assert_awaited_once_with(
        sandbox_id="sandbox-test-123",
        api_key="test-api-key",
        headers={"E2b-Sandbox-Id": "sandbox-test-123", "E2b-Sandbox-Port": "49983"},
    )

    mock_e2b_module.connect.side_effect = RuntimeError("sandbox gone")
    assert await backend.is_session_alive(info) is False


@pytest.mark.anyio
async def test_start_session_with_template(backend, mock_e2b_module):
    """start_session passes template parameter when image is specified."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(
        session_id="sess2",
        cmd="python script.py",
        image="python-3.11",
    )

    info = await backend.start_session(spec)

    assert info.image == "python-3.11"

    # Verify template was passed
    call_kwargs = mock_e2b_module.create.call_args.kwargs
    assert call_kwargs.get("template") == "python-3.11"


@pytest.mark.anyio
async def test_start_session_with_envs(backend, mock_e2b_module):
    """start_session passes environment variables."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(
        session_id="sess3",
        cmd="echo $FOO",
        env={"FOO": "bar", "DEBUG": "1"},
    )

    await backend.start_session(spec)

    call_kwargs = mock_e2b_module.create.call_args.kwargs
    assert call_kwargs.get("envs") == {"FOO": "bar", "DEBUG": "1"}


@pytest.mark.anyio
async def test_start_session_with_api_url(backend, mock_e2b_module):
    """start_session passes domain for CubeSandbox self-deployment."""
    backend._api_key = "dummy"
    backend._api_url = "http://127.0.0.1:3000"
    spec = BoxSpec(session_id="sess4", cmd="ls")

    await backend.start_session(spec)

    call_kwargs = mock_e2b_module.create.call_args.kwargs
    assert call_kwargs.get("domain") == "http://127.0.0.1:3000"


@pytest.mark.anyio
async def test_start_session_custom_mount_path(backend, mock_e2b_module):
    """start_session adapts custom mount_path."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(
        session_id="sess5",
        cmd="ls",
        mount_path="/workspace/myproject",
    )

    info = await backend.start_session(spec)

    # Session metadata keeps the logical mount path; command execution adapts
    # it to E2B's internal writable path.
    assert info.mount_path == "/workspace/myproject"


# ── CubeSandbox host-mount metadata ───────────────────────────────────


@pytest.mark.anyio
async def test_start_session_host_mount_rw(backend, mock_e2b_module):
    """host_path with rw mode generates correct metadata."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(
        session_id="sess-hp-rw",
        cmd="ls",
        host_path="/data/project",
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/workspace",
    )

    await backend.start_session(spec)

    call_kwargs = mock_e2b_module.create.call_args.kwargs
    metadata = call_kwargs.get("metadata", {})

    assert "host-mount" in metadata
    host_mount = json.loads(metadata["host-mount"])
    assert len(host_mount) == 1
    assert host_mount[0]["hostPath"] == "/data/project"
    # mountPath should be adapted
    assert host_mount[0]["mountPath"] == "/home/user/workspace"
    assert host_mount[0]["readOnly"] is False


@pytest.mark.anyio
async def test_start_session_host_mount_ro(backend, mock_e2b_module):
    """host_path with ro mode generates readOnly=True in metadata."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(
        session_id="sess-hp-ro",
        cmd="cat file.txt",
        host_path="/data/source",
        host_path_mode=BoxHostMountMode.READ_ONLY,
        mount_path="/src",  # Non-workspace path stays unchanged
    )

    await backend.start_session(spec)

    call_kwargs = mock_e2b_module.create.call_args.kwargs
    metadata = call_kwargs.get("metadata", {})

    host_mount = json.loads(metadata["host-mount"])
    assert host_mount[0]["readOnly"] is True
    # Non-workspace path stays unchanged
    assert host_mount[0]["mountPath"] == "/src"


@pytest.mark.anyio
async def test_start_session_no_host_mount_when_none(backend, mock_e2b_module):
    """host_path_mode=none skips host-mount metadata."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(
        session_id="sess-hp-none",
        cmd="ls",
        host_path="/data",
        host_path_mode=BoxHostMountMode.NONE,
    )

    await backend.start_session(spec)

    call_kwargs = mock_e2b_module.create.call_args.kwargs
    assert "host-mount" not in call_kwargs.get("metadata", {})


@pytest.mark.anyio
async def test_start_session_no_host_mount_when_empty(backend, mock_e2b_module):
    """Empty host_path skips host-mount metadata."""
    backend._api_key = "test-api-key"
    spec = BoxSpec(session_id="sess-no-hp", cmd="ls")

    await backend.start_session(spec)

    call_kwargs = mock_e2b_module.create.call_args.kwargs
    assert "metadata" not in call_kwargs or "host-mount" not in call_kwargs.get(
        "metadata", {}
    )


# ── exec ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize("sandbox_id", ["sandbox-123", "sandbox-456"])
async def test_exec_success(backend, mock_e2b_module, sandbox_id):
    """exec runs command and returns result."""
    backend._api_key = "test-api-key"

    session = BoxSessionInfo(
        session_id="exec-sess",
        backend_name="e2b",
        backend_session_id=sandbox_id,
        image="base",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(
        session_id="exec-sess",
        cmd="echo hello",
        workdir="/workspace",
        env={"FOO": "bar"},
    )

    result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "output"

    # Verify connect and run were called
    mock_e2b_module.connect.assert_awaited_once_with(
        sandbox_id=sandbox_id,
        api_key="test-api-key",
        headers={"E2b-Sandbox-Id": sandbox_id, "E2b-Sandbox-Port": "49983"},
    )
    mock_e2b_module.commands.run.assert_called_once()

    # Verify command includes path adaptation
    run_kwargs = mock_e2b_module.commands.run.call_args.kwargs
    assert "/home/user/workspace" in run_kwargs["cmd"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mount_kind", ["read_only_primary", "read_write_primary", "read_only_extra"]
)
async def test_exec_syncs_mounts_before_running_command(
    backend, mock_e2b_module, tmp_path, mount_kind
):
    """Exercise the real sync dispatch, including immutable materialization."""
    (tmp_path / "input.txt").write_text("input", encoding="utf-8")
    spec = BoxSpec(session_id="exec-mount", cmd="cat /workspace/input.txt")
    if mount_kind == "read_only_extra":
        spec.extra_mounts = [
            BoxMountSpec(
                host_path=str(tmp_path),
                mount_path="/workspace",
                mode=BoxHostMountMode.READ_ONLY,
            )
        ]
    else:
        spec.host_path = str(tmp_path)
        spec.host_path_mode = (
            BoxHostMountMode.READ_ONLY
            if mount_kind == "read_only_primary"
            else BoxHostMountMode.READ_WRITE
        )
    mock_e2b_module.files = SimpleNamespace(
        write=mock.AsyncMock(), list=mock.AsyncMock(return_value=[])
    )
    session = await backend.start_session(spec)

    result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    commands = mock_e2b_module.commands.run.await_args_list
    assert commands[-1].kwargs["cmd"].endswith("cat /home/user/workspace/input.txt")
    writes = mock_e2b_module.files.write.await_args_list
    assert writes[0].args[1] == b"input"
    if mount_kind == "read_write_primary":
        assert writes[0].args[0] == "/home/user/workspace/input.txt"
        assert len(writes) == 1
        mock_e2b_module.files.list.assert_awaited_once_with(
            "/home/user/workspace", depth=16
        )
    else:
        assert writes[0].args[0].endswith("/package/input.txt")
        assert (
            len(writes) == 2
        )  # package file and manifest; root writes the ready marker
        setup_commands = "\n".join(call.args[0] for call in commands[:-1])
        assert setup_commands.index("python3 -c") < setup_commands.index("ln -s")
        mock_e2b_module.files.list.assert_not_awaited()


@pytest.mark.anyio
async def test_exec_writable_primary_excludes_shadowed_extra_mounts(
    backend, mock_e2b_module, tmp_path
):
    workspace = tmp_path / "workspace"
    shadowed = workspace / ".skills" / "demo"
    shadowed.mkdir(parents=True)
    (shadowed / "stale.txt").write_text("shadowed", encoding="utf-8")
    (workspace / ".skills" / "demo.txt").write_text("sibling", encoding="utf-8")
    (workspace / "notes.txt").write_text("notes", encoding="utf-8")
    revision = tmp_path / "revision"
    revision.mkdir()
    (revision / "run.py").write_text("print('ok')", encoding="utf-8")
    spec = BoxSpec(
        session_id="exec-overlay",
        cmd="python /workspace/.skills/demo/run.py",
        host_path=str(workspace),
        host_path_mode=BoxHostMountMode.READ_WRITE,
        extra_mounts=[
            BoxMountSpec(
                host_path=str(revision),
                mount_path="/workspace/.skills/demo",
                mode=BoxHostMountMode.READ_ONLY,
            )
        ],
    )
    mock_e2b_module.files = SimpleNamespace(
        write=mock.AsyncMock(),
        write_files=mock.AsyncMock(),
        list=mock.AsyncMock(
            return_value=[
                SimpleNamespace(
                    path="/home/user/workspace/.skills/demo/run.py",
                    size=11,
                    type=SimpleNamespace(value="file"),
                )
            ]
        ),
        read=mock.AsyncMock(),
    )
    session = await backend.start_session(spec)

    result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    writes = mock_e2b_module.files.write.await_args_list
    uploaded_paths = [call.args[0] for call in writes]
    uploaded_paths.extend(
        entry["path"]
        for call in mock_e2b_module.files.write_files.await_args_list
        for entry in call.args[0]
    )
    assert "/home/user/workspace/notes.txt" in uploaded_paths
    assert "/home/user/workspace/.skills/demo.txt" in uploaded_paths
    assert not any(path.endswith("/stale.txt") for path in uploaded_paths)
    assert any(path.endswith("/package/run.py") for path in uploaded_paths)
    assert (
        mock_e2b_module.commands.run.await_args_list[-1]
        .kwargs["cmd"]
        .endswith("python /home/user/workspace/.skills/demo/run.py")
    )
    mock_e2b_module.files.read.assert_not_awaited()
    assert not (shadowed / "run.py").exists()


@pytest.mark.anyio
async def test_exec_timeout(backend, mock_e2b_module):
    """exec handles timeout correctly."""
    backend._api_key = "test-api-key"

    # Mock timeout error
    mock_e2b_module.commands.run = mock.AsyncMock(
        side_effect=Exception("Command timed out after 30 seconds")
    )

    session = BoxSessionInfo(
        session_id="timeout-sess",
        backend_name="e2b",
        backend_session_id="sandbox-456",
        image="base",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(session_id="timeout-sess", cmd="sleep 100", timeout_sec=30)

    result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert "timed out" in result.stderr.lower()


@pytest.mark.anyio
async def test_exec_truncates_large_output(backend, mock_e2b_module):
    """exec truncates output exceeding the limit."""
    backend._api_key = "test-api-key"

    # Create large output (over 1MB)
    large_output = "x" * (2 * 1024 * 1024)  # 2MB
    mock_command_result = mock.MagicMock()
    mock_command_result.stdout = large_output
    mock_command_result.stderr = ""
    mock_command_result.exit_code = 0

    mock_commands = mock.MagicMock()
    mock_commands.run = mock.AsyncMock(return_value=mock_command_result)
    mock_e2b_module.commands = mock_commands

    session = BoxSessionInfo(
        session_id="truncate-sess",
        backend_name="e2b",
        backend_session_id="sandbox-789",
        image="base",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(session_id="truncate-sess", cmd="cat large_file")

    result = await backend.exec(session, spec)

    assert "clipped" in result.stdout


@pytest.mark.anyio
async def test_writable_upload_batches_are_bounded(backend, tmp_path, monkeypatch):
    import langbot_plugin.box.e2b_backend as module

    monkeypatch.setattr(module, "_E2B_UPLOAD_BATCH_FILES", 2)
    monkeypatch.setattr(module, "_E2B_UPLOAD_BATCH_BYTES", 6)
    monkeypatch.setattr(module, "_MAX_E2B_SYNC_FILES", 5)
    for i in range(7):
        (tmp_path / f"{i}.txt").write_bytes(b"data")
    files = SimpleNamespace(write=mock.AsyncMock(), write_files=mock.AsyncMock())
    sandbox = SimpleNamespace(
        files=files, commands=SimpleNamespace(run=mock.AsyncMock())
    )

    await backend._sync_host_tree_to_e2b(
        sandbox, host_root=str(tmp_path), remote_root="/remote"
    )

    entries = [
        {"path": c.args[0], "data": c.args[1]} for c in files.write.await_args_list
    ]
    for call in files.write_files.await_args_list:
        assert len(call.args[0]) <= 2
        assert sum(len(e["data"]) for e in call.args[0]) <= 6
        entries.extend(call.args[0])
    assert len(entries) == 5
    assert all(e["data"] == b"data" for e in entries)


@pytest.mark.anyio
async def test_writable_upload_batches_and_recovers_independent_files(
    backend, tmp_path
):
    for i in range(70):
        (tmp_path / f"{i}.txt").write_bytes(b"data")
    files = SimpleNamespace(write=mock.AsyncMock(), write_files=mock.AsyncMock())
    sandbox = SimpleNamespace(
        files=files, commands=SimpleNamespace(run=mock.AsyncMock())
    )
    await backend._sync_host_tree_to_e2b(
        sandbox, host_root=str(tmp_path), remote_root="/remote"
    )
    batches = [c.args[0] for c in files.write_files.await_args_list]
    assert [len(batch) for batch in batches] == [32, 32, 6]
    files.write.assert_not_awaited()
    assert {e["path"] for batch in batches for e in batch} == {
        f"/remote/{i}.txt" for i in range(70)
    }

    uploaded = {}

    async def write(path, data):
        if path == "/remote/0.txt":
            raise OSError("one file rejected")
        uploaded[path] = data

    files.write.side_effect = write
    files.write_files.side_effect = OSError("batch rejected")
    await backend._sync_host_tree_to_e2b(
        sandbox, host_root=str(tmp_path), remote_root="/remote"
    )
    assert files.write.await_count == 70
    assert uploaded == {f"/remote/{i}.txt": b"data" for i in range(1, 70)}


@pytest.mark.anyio
async def test_remote_download_concurrency_and_independent_failure(backend, tmp_path):
    active = 0
    peak = 0

    class Files:
        async def list(self, root, depth):
            return [
                SimpleNamespace(
                    path=f"{root}/{i}.txt", size=4, type=SimpleNamespace(value="file")
                )
                for i in range(20)
            ]

        async def read(self, path, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)

            async def chunks():
                nonlocal active
                try:
                    await asyncio.sleep(0.001)
                    if path == "/remote/0.txt":
                        raise OSError("one download failed")
                    yield b"data"
                finally:
                    active -= 1

            return chunks()

    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=Files()), host_root=str(tmp_path), remote_root="/remote"
    )
    assert 1 < peak <= 8
    assert active == 0
    assert not (tmp_path / "0.txt").exists()
    assert all((tmp_path / f"{i}.txt").read_bytes() == b"data" for i in range(1, 20))


@pytest.mark.anyio
async def test_concurrent_downloads_share_total_byte_budget(
    backend, tmp_path, monkeypatch
):
    import langbot_plugin.box.e2b_backend as module

    monkeypatch.setattr(module, "_MAX_E2B_SYNC_TOTAL_BYTES", 6)

    class Files:
        async def list(self, root, depth):
            return [
                SimpleNamespace(
                    path=f"{root}/{i}.txt", size=0, type=SimpleNamespace(value="file")
                )
                for i in range(10)
            ]

        async def read(self, path, **kwargs):
            async def chunks():
                await asyncio.sleep(0.001)
                yield b"1234"

            return chunks()

    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=Files()), host_root=str(tmp_path), remote_root="/remote"
    )
    assert len(list(tmp_path.iterdir())) == 1
    assert sum(p.stat().st_size for p in tmp_path.iterdir()) <= 6


@pytest.mark.anyio
async def test_concurrent_downloads_keep_path_and_file_count_limits(
    backend, tmp_path, monkeypatch
):
    import langbot_plugin.box.e2b_backend as module

    monkeypatch.setattr(module, "_MAX_E2B_SYNC_FILES", 2)
    paths = [
        "/remote/../../outside.txt",
        "/other/x",
        "/remote/a",
        "/remote/b",
        "/remote/c",
    ]

    async def read(path, **kwargs):
        async def chunks():
            yield path.encode()

        return chunks()

    files = SimpleNamespace(
        list=mock.AsyncMock(
            return_value=[
                SimpleNamespace(path=p, size=0, type=SimpleNamespace(value="file"))
                for p in paths
            ]
        ),
        read=mock.AsyncMock(side_effect=read),
    )
    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=files), host_root=str(tmp_path), remote_root="/remote"
    )
    assert {call.args[0] for call in files.read.await_args_list} == {
        "/remote/a",
        "/remote/b",
    }
    assert {p.name for p in tmp_path.iterdir()} == {"a", "b"}


@pytest.mark.anyio
async def test_download_aliases_keep_sequential_write_order(backend, tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).symlink_to("target")
    active = 0
    peak = 0
    completed = []

    class Files:
        async def list(self, root, depth):
            return [
                SimpleNamespace(
                    path=f"{root}/{name}", size=1, type=SimpleNamespace(value="file")
                )
                for name in ("a", "b")
            ]

        async def read(self, path, **kwargs):
            async def chunks():
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                try:
                    await asyncio.sleep(0.01 if path.endswith("/a") else 0.001)
                    yield path[-1:].encode()
                    completed.append(path[-1:])
                finally:
                    active -= 1

            return chunks()

    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=Files()), host_root=str(tmp_path), remote_root="/remote"
    )
    assert peak == 2
    assert completed == ["b", "a"]
    assert (tmp_path / "target").read_bytes() == b"b"


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["stream", "write"])
async def test_failed_download_does_not_consume_successful_byte_budget(
    backend, tmp_path, monkeypatch, failure
):
    import langbot_plugin.box.e2b_backend as module

    monkeypatch.setattr(module, "_MAX_E2B_SYNC_TOTAL_BYTES", 6)
    original_write = module._write_e2b_host_file

    def write(path, data):
        if failure == "write" and path.endswith("/a"):
            raise OSError("disk write rejected")
        original_write(path, data)

    monkeypatch.setattr(module, "_write_e2b_host_file", write)

    class Files:
        async def list(self, root, depth):
            return [
                SimpleNamespace(
                    path=f"{root}/{name}", size=0, type=SimpleNamespace(value="file")
                )
                for name in ("a", "b")
            ]

        async def read(self, path, **kwargs):
            async def chunks():
                yield b"bad!" if path.endswith("/a") else b"good"
                if path.endswith("/a"):
                    await asyncio.sleep(0.01)
                    if failure == "stream":
                        raise OSError("stream interrupted after a chunk")

            return chunks()

    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=Files()), host_root=str(tmp_path), remote_root="/remote"
    )
    assert not (tmp_path / "a").exists()
    assert (tmp_path / "b").read_bytes() == b"good"


@pytest.mark.anyio
async def test_byte_limit_keeps_listing_order_not_download_completion_order(
    backend, tmp_path, monkeypatch
):
    import langbot_plugin.box.e2b_backend as module

    monkeypatch.setattr(module, "_MAX_E2B_SYNC_TOTAL_BYTES", 6)
    bodies = {"a": b"aaaa", "b": b"bbbb", "c": b"cc"}

    class Files:
        async def list(self, root, depth):
            return [
                SimpleNamespace(
                    path=f"{root}/{name}", size=0, type=SimpleNamespace(value="file")
                )
                for name in bodies
            ]

        async def read(self, path, **kwargs):
            async def chunks():
                if path.endswith("/a"):
                    await asyncio.sleep(0.01)
                yield bodies[path.rsplit("/", 1)[-1]]

            return chunks()

    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=Files()), host_root=str(tmp_path), remote_root="/remote"
    )
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == {
        "a": b"aaaa",
        "c": b"cc",
    }


@pytest.mark.anyio
async def test_failed_download_does_not_use_file_count_slot(
    backend, tmp_path, monkeypatch
):
    import langbot_plugin.box.e2b_backend as module

    monkeypatch.setattr(module, "_MAX_E2B_SYNC_FILES", 2)

    class Files:
        async def list(self, root, depth):
            return [
                SimpleNamespace(
                    path=f"{root}/{name}", size=1, type=SimpleNamespace(value="file")
                )
                for name in ("a", "b", "c")
            ]

        async def read(self, path, **kwargs):
            if path.endswith("/a"):
                raise OSError("file unavailable")

            async def chunks():
                yield path[-1:].encode()

            return chunks()

    await backend._sync_e2b_tree_to_host(
        SimpleNamespace(files=Files()), host_root=str(tmp_path), remote_root="/remote"
    )
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == {
        "b": b"b",
        "c": b"c",
    }


# ── stop_session ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_stop_session(backend, mock_e2b_module):
    """stop_session kills the sandbox."""
    backend._api_key = "test-api-key"

    session = BoxSessionInfo(
        session_id="stop-sess",
        backend_name="e2b",
        backend_session_id="sandbox-to-kill",
        image="base",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )

    await backend.stop_session(session)

    # Verify AsyncSandbox.kill was called
    mock_e2b_module.kill.assert_called_once()


@pytest.mark.anyio
async def test_stop_session_handles_error(backend, mock_e2b_module):
    """stop_session logs error but doesn't raise on kill failure."""
    backend._api_key = "test-api-key"

    mock_e2b_module.kill = mock.AsyncMock(side_effect=Exception("Sandbox not found"))

    session = BoxSessionInfo(
        session_id="stop-fail",
        backend_name="e2b",
        backend_session_id="sandbox-missing",
        image="base",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )

    # Should not raise
    await backend.stop_session(session)


@pytest.mark.anyio
async def test_remote_sync_stream_is_bounded(backend, tmp_path, monkeypatch):
    import langbot_plugin.box.e2b_backend as e2b_backend

    monkeypatch.setattr(e2b_backend, "_MAX_E2B_SYNC_FILE_BYTES", 4)

    class Files:
        async def list(self, _root, depth):
            assert depth == 16
            return [
                SimpleNamespace(
                    path="/remote/large.bin",
                    size=0,
                    type=SimpleNamespace(value="file"),
                )
            ]

        async def read(self, _path, *, format, request_timeout):
            assert format == "stream"
            assert request_timeout == 30

            async def chunks():
                yield b"123"
                yield b"45"

            return chunks()

    sandbox = SimpleNamespace(files=Files())
    await backend._sync_e2b_tree_to_host(
        sandbox,
        remote_root="/remote",
        host_root=str(tmp_path),
    )

    assert not (tmp_path / "large.bin").exists()


@pytest.mark.anyio
async def test_immutable_mount_is_verified_before_projection(backend, tmp_path):
    (tmp_path / "SKILL.md").write_text("instructions", encoding="utf-8")
    (tmp_path / "run.py").write_text("print('ok')", encoding="utf-8")
    digest, manifest = _build_e2b_host_manifest(str(tmp_path))
    manifest_path = tmp_path.with_name(f"{tmp_path.name}-manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    commands = SimpleNamespace(
        run=mock.AsyncMock(
            return_value=SimpleNamespace(exit_code=0, stdout="", stderr="")
        )
    )
    files = SimpleNamespace(write=mock.AsyncMock())
    sandbox = SimpleNamespace(commands=commands, files=files)

    with mock.patch(
        "langbot_plugin.box.e2b_backend._build_e2b_host_manifest",
        side_effect=AssertionError("published mounts must use their manifest"),
    ):
        await backend._materialize_immutable_mount(
            sandbox,
            host_root=str(tmp_path),
            remote_root="/home/user/workspace/.skills/demo",
            expected_digest=digest,
            manifest_path=str(manifest_path),
        )

    commands_text = "\n".join(call.args[0] for call in commands.run.await_args_list)
    verify_index = commands_text.index("python3 -c")
    publish_index = commands_text.index("mv ")
    projection_index = commands_text.index("ln -s")
    assert (
        commands_text.index("cp -R -P")
        < verify_index
        < publish_index
        < projection_index
    )
    assert files.write.await_count == 3  # two package files and manifest


@pytest.mark.anyio
async def test_interrupted_immutable_transfer_never_projects_partial_tree(
    backend,
    tmp_path,
):
    (tmp_path / "SKILL.md").write_text("instructions", encoding="utf-8")
    (tmp_path / "run.py").write_text("print('ok')", encoding="utf-8")
    digest, _manifest = _build_e2b_host_manifest(str(tmp_path))
    commands = SimpleNamespace(
        run=mock.AsyncMock(
            return_value=SimpleNamespace(exit_code=0, stdout="", stderr="")
        )
    )
    files = SimpleNamespace(
        write=mock.AsyncMock(side_effect=[None, OSError("upload interrupted")])
    )
    sandbox = SimpleNamespace(commands=commands, files=files)

    with pytest.raises(BoxError, match="materialize immutable E2B mount"):
        await backend._materialize_immutable_mount(
            sandbox,
            host_root=str(tmp_path),
            remote_root="/home/user/workspace/.skills/demo",
            expected_digest=digest,
        )

    commands_text = "\n".join(call.args[0] for call in commands.run.await_args_list)
    assert "ln -s" not in commands_text
    assert "staging" in commands_text and "rm -rf" in commands_text


@pytest.mark.anyio
async def test_immutable_mount_rejects_declared_digest_mismatch(backend, tmp_path):
    (tmp_path / "SKILL.md").write_text("instructions", encoding="utf-8")
    sandbox = SimpleNamespace(
        commands=SimpleNamespace(run=mock.AsyncMock()),
        files=SimpleNamespace(write=mock.AsyncMock()),
    )

    with pytest.raises(BoxError, match="does not match"):
        await backend._materialize_immutable_mount(
            sandbox,
            host_root=str(tmp_path),
            remote_root="/home/user/workspace/.skills/demo",
            expected_digest="sha256:" + "0" * 64,
        )

    sandbox.files.write.assert_not_awaited()


@pytest.mark.anyio
async def test_box_restart_reuses_only_verified_ready_revision(backend, tmp_path):
    (tmp_path / "SKILL.md").write_text("instructions", encoding="utf-8")
    digest, manifest = _build_e2b_host_manifest(str(tmp_path))
    manifest_path = tmp_path.with_name(f"{tmp_path.name}-manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    success = SimpleNamespace(exit_code=0, stdout="", stderr="")
    commands = SimpleNamespace(
        run=mock.AsyncMock(
            side_effect=[
                SimpleNamespace(exit_code=0, stdout=digest, stderr=""),
                success,
                success,
            ]
        )
    )
    sandbox = SimpleNamespace(
        commands=commands,
        files=SimpleNamespace(write=mock.AsyncMock()),
    )

    await backend._materialize_immutable_mount(
        sandbox,
        host_root=str(tmp_path),
        remote_root="/home/user/workspace/.skills/demo",
        expected_digest=digest,
        manifest_path=str(manifest_path),
    )

    sandbox.files.write.assert_not_awaited()
    commands_text = "\n".join(call.args[0] for call in commands.run.await_args_list)
    assert "python3 -c" in commands_text
    assert "ln -s" in commands_text
    assert "staging-" not in commands_text


# ── _check_e2b_available ──────────────────────────────────────────────


def test_check_e2b_available_caches_result():
    """_check_e2b_available caches the import check result."""
    # Reset the cache
    import langbot_plugin.box.e2b_backend as e2b_backend

    e2b_backend._e2b_available = None

    # First call
    with mock.patch.dict("sys.modules", {"e2b": mock.MagicMock()}):
        result1 = _check_e2b_available()

    # Second call should use cached result
    result2 = _check_e2b_available()

    assert result1 == result2


def test_check_e2b_available_returns_false_on_import_error():
    """_check_e2b_available returns False when import fails."""
    import langbot_plugin.box.e2b_backend as e2b_backend

    e2b_backend._e2b_available = None
    e2b_backend._AsyncSandbox = None

    with mock.patch("builtins.__import__", side_effect=ImportError("No e2b")):
        result = _check_e2b_available()

    assert result is False


@pytest.mark.anyio
async def test_verifier_rejects_symlink_package_root_and_manifest(backend, tmp_path):
    import asyncio

    package = tmp_path / "package"
    package.mkdir()
    (package / "value").write_text("expected")
    digest, manifest = _build_e2b_host_manifest(str(package))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    async def run(command, **kwargs):
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return SimpleNamespace(
            exit_code=process.returncode, stdout=stdout.decode(), stderr=stderr.decode()
        )

    sandbox = SimpleNamespace(commands=SimpleNamespace(run=run))
    await backend._verify_remote_manifest(
        sandbox,
        package_root=str(package),
        manifest_path=str(manifest_path),
        expected_digest=digest,
    )
    alias = tmp_path / "alias"
    alias.symlink_to(package, target_is_directory=True)
    with pytest.raises(BoxError):
        await backend._verify_remote_manifest(
            sandbox,
            package_root=str(alias),
            manifest_path=str(manifest_path),
            expected_digest=digest,
        )
    alias.unlink()
    alias.symlink_to(manifest_path)
    with pytest.raises(BoxError):
        await backend._verify_remote_manifest(
            sandbox,
            package_root=str(package),
            manifest_path=str(alias),
            expected_digest=digest,
        )


@pytest.mark.anyio
async def test_cancelled_upload_cleans_staging_without_publication(backend, tmp_path):
    import asyncio

    (tmp_path / "file").write_text("data")
    sandbox = SimpleNamespace(
        files=SimpleNamespace(
            write=mock.AsyncMock(side_effect=asyncio.CancelledError())
        ),
        commands=SimpleNamespace(
            run=mock.AsyncMock(
                return_value=SimpleNamespace(exit_code=0, stdout="", stderr="")
            )
        ),
    )
    with pytest.raises(asyncio.CancelledError):
        await backend._materialize_immutable_mount(
            sandbox, host_root=str(tmp_path), remote_root="/test-package"
        )
    calls = [call.args[0] for call in sandbox.commands.run.await_args_list]
    assert "rm -rf" in calls[-1]
    assert ".sealed" in calls[-1]
    assert not any("ln -s" in command or "mv " in command for command in calls)


@pytest.mark.asyncio
async def test_workspace_connections_ignore_deployment_env_and_hide_provider_key_errors(
    logger, monkeypatch, caplog
):
    from langbot_plugin.box import e2b_backend as module
    from langbot_plugin.box.models import E2BConnectionConfig
    from langbot_plugin.box.runtime import BoxRuntime

    monkeypatch.setenv("E2B_API_KEY", "deployment-key")
    monkeypatch.setenv("E2B_API_URL", "http://deployment-api.test")
    monkeypatch.setenv("E2B_SANDBOX_URL", "http://deployment-sandbox.test")
    a = E2BConnectionConfig(
        api_url="http://a-api.test",
        sandbox_url="http://a-sandbox.test",
        api_key="private-a",
        template="base",
    )
    b = E2BConnectionConfig(
        api_url="http://b-api.test",
        sandbox_url="http://b-sandbox.test",
        api_key="private-b",
        template="base",
    )
    assert a.api_key not in repr(a)
    sandboxes = [
        SimpleNamespace(sandbox_id="sandbox-a"),
        SimpleNamespace(sandbox_id="sandbox-b"),
    ]
    api = SimpleNamespace(
        create=mock.AsyncMock(side_effect=sandboxes), kill=mock.AsyncMock()
    )
    monkeypatch.setattr(module, "_check_e2b_available", lambda: True)
    monkeypatch.setattr(module, "_AsyncSandbox", api)
    runtime = BoxRuntime(logger, backends=[], session_ttl_sec=0)
    try:
        await runtime.create_session(
            BoxSpec(session_id="a", backend="e2b", e2b_config=a)
        )
        await runtime.create_session(
            BoxSpec(session_id="b", backend="e2b", e2b_config=b)
        )
        calls = api.create.await_args_list
        assert (
            calls[0].kwargs["api_key"] == "private-a"
            and calls[0].kwargs["api_url"] == a.api_url
        )
        assert calls[0].kwargs["sandbox_url"] == a.sandbox_url
        assert (
            calls[1].kwargs["api_key"] == "private-b"
            and calls[1].kwargs["api_url"] == b.api_url
        )
        from langbot_plugin.box.errors import BoxSessionConflictError

        with pytest.raises(BoxSessionConflictError):
            await runtime.create_session(
                BoxSpec(session_id="a", backend="e2b", e2b_config=b)
            )
        await runtime.delete_session("a")
        assert api.kill.await_args.kwargs["api_key"] == "private-a"
        assert api.kill.await_args.kwargs["api_url"] == a.api_url
        api.create.side_effect = RuntimeError("upstream leaked private-a")
        with pytest.raises(BoxError) as caught:
            await runtime.create_session(
                BoxSpec(session_id="failed", backend="e2b", e2b_config=a)
            )
        import traceback

        assert "private-a" not in "".join(traceback.format_exception(caught.value))
        assert "private-a" not in caplog.text
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "create", "execute", "cleanup", "cancel"])
async def test_template_check_uses_supplied_template_and_cleans_up(
    logger, mock_e2b_module, failure
):
    import asyncio
    from langbot_plugin.box.models import E2BConnectionConfig

    config = E2BConnectionConfig(
        api_url="http://api.test",
        sandbox_url="http://proxy.test",
        api_key="private-key",
        template="user-template",
    )
    backend = E2BSandboxBackend(logger, connection_config=config)
    await backend.initialize()

    async def run(command, **kwargs):
        if failure == "cancel":
            raise asyncio.CancelledError()
        if failure == "execute":
            raise RuntimeError("private-key")
        return SimpleNamespace(exit_code=0, stdout=command.removeprefix("printf "))

    mock_e2b_module.commands.run.side_effect = run
    if failure == "create":
        mock_e2b_module.create.side_effect = RuntimeError("private-key")
    if failure == "cleanup":
        mock_e2b_module.kill.side_effect = RuntimeError("private-key")
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await backend.inspect_template()
    else:
        result = await backend.inspect_template()
        assert result["template_validated"] == (failure is None)
        assert "private-key" not in json.dumps(result)
    assert mock_e2b_module.create.await_args.kwargs["template"] == "user-template"
    if failure == "create":
        mock_e2b_module.kill.assert_not_called()
    else:
        mock_e2b_module.kill.assert_awaited_once()


def test_workspace_template_overrides_task_image():
    from langbot_plugin.box.models import E2BConnectionConfig

    config = E2BConnectionConfig(
        api_url="http://api.test",
        sandbox_url="http://proxy.test",
        api_key="private",
        template="chosen-template",
    )
    assert (
        BoxSpec(
            session_id="configured-template",
            backend="e2b",
            e2b_config=config,
            image="docker-image",
        ).image
        == "chosen-template"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,available,validation,reason",
    [
        ("ready", True, "ready", None),
        ("building", False, "not_ready", "template_not_ready"),
        ("disabled", True, "unsupported", None),
        ("not_found", False, "not_found", "template_not_found"),
        ("forbidden", False, "failed", "permission_denied"),
    ],
)
async def test_lightweight_template_check_never_creates(
    logger, mock_e2b_module, case, available, validation, reason
):
    import httpx
    from langbot_plugin.box.models import E2BConnectionConfig

    config = E2BConnectionConfig(
        api_url="https://api.test",
        sandbox_url="https://proxy.test",
        api_key="private-key",
        template="chosen",
    )
    backend = E2BSandboxBackend(logger, connection_config=config)
    await backend.initialize()
    mock_e2b_module.list.return_value.next_items = mock.AsyncMock(return_value=[])
    paths = []

    def respond(request):
        paths.append(request.url.path)
        assert request.headers["X-API-Key"] == "private-key"
        if case == "disabled":
            return httpx.Response(404, json={"message": "route is disabled by profile"})
        if case == "forbidden":
            return httpx.Response(
                403, json={"message": "private-key provider diagnostic"}
            )
        if request.url.path.startswith("/templates/aliases/"):
            return httpx.Response(
                200, json={"templateID": "resolved-id", "public": False}
            )
        if case == "not_found":
            return httpx.Response(404, json={"message": "Template not found"})
        return httpx.Response(
            200,
            json={"builds": [{"status": "ready" if case == "ready" else "building"}]},
        )

    real_client = httpx.AsyncClient
    with mock.patch(
        "langbot_plugin.box.e2b_backend.httpx.AsyncClient",
        side_effect=lambda **kw: real_client(
            transport=httpx.MockTransport(respond), **kw
        ),
    ):
        result = await backend.inspect_template(validate=False)
    assert result["available"] is available
    assert result["template_validation"] == validation
    assert result["reason"] == reason
    assert result["template_validated"] is False
    assert "private-key" not in json.dumps(result)
    mock_e2b_module.create.assert_not_called()
    mock_e2b_module.kill.assert_not_called()
    assert paths[0] == "/templates/aliases/chosen"
    if case != "forbidden":
        assert paths[-1] == (
            "/templates/chosen" if case == "disabled" else "/templates/resolved-id"
        )


@pytest.mark.parametrize(
    "status,stage,expected",
    [
        (401, "template_query_failed", "authentication_failed"),
        (403, "template_creation_failed", "permission_denied"),
        (404, "template_query_failed", "template_not_found"),
        (404, "connection_failed", "resource_not_found"),
        (429, "template_creation_failed", "capacity_limited"),
        (429, "template_query_failed", "rate_limited"),
    ],
)
def test_e2b_failure_classification_uses_status_without_echoing_body(
    status, stage, expected
):
    from e2b.exceptions import SandboxException

    assert (
        E2BSandboxBackend._failure_reason(
            SandboxException(f"{status}: private-key"), stage
        )
        == expected
    )


@pytest.mark.anyio
async def test_upload_cancellation_waits_for_remote_publication_and_cleanup(
    backend, mock_e2b_module
):
    session = await backend.start_session(BoxSpec(session_id="file-cancel", cmd="true"))
    publication_started = asyncio.Event()
    allow_publication = asyncio.Event()
    cleanup_started = asyncio.Event()
    allow_cleanup = asyncio.Event()
    events = []

    async def run(command, **kwargs):
        if command.startswith("python3 -c"):
            publication_started.set()
            await allow_publication.wait()
            events.append("published")
        elif command.startswith("rm -rf --"):
            cleanup_started.set()
            await allow_cleanup.wait()
            events.append("cleaned")
        return SimpleNamespace(exit_code=0, stdout="", stderr="")

    mock_e2b_module.commands.run = mock.AsyncMock(side_effect=run)
    mock_e2b_module.files = SimpleNamespace(write=mock.AsyncMock())
    upload = asyncio.create_task(
        backend.upload_file(session, "/workspace/input.bin", b"payload", 1024)
    )
    try:
        await asyncio.wait_for(publication_started.wait(), timeout=1)
        upload.cancel()
        await asyncio.sleep(0)
        assert not upload.done()
        assert not cleanup_started.is_set()
        upload.cancel()
        await asyncio.sleep(0)
        assert not upload.done()
        allow_publication.set()
        await asyncio.wait_for(cleanup_started.wait(), timeout=1)
        upload.cancel()
        await asyncio.sleep(0)
        assert not upload.done()
        allow_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(upload, timeout=1)
        assert events == ["published", "cleaned"]
    finally:
        allow_publication.set()
        allow_cleanup.set()
        await asyncio.gather(upload, return_exceptions=True)


@pytest.mark.anyio
async def test_upload_publishes_bytes_with_private_staging(
    backend, mock_e2b_module, tmp_path, monkeypatch
):
    import os
    from pathlib import Path
    import shlex
    import sys
    from langbot_plugin.box import e2b_backend

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(e2b_backend, "_adapt_path_for_e2b", lambda path: str(workspace))
    session = await backend.start_session(BoxSpec(session_id="file-owner", cmd="true"))

    async def write(path, content, **kwargs):
        Path(path).write_bytes(content)

    async def run(command, **kwargs):
        args = shlex.split(command)
        if args[:2] == ["python3", "-c"]:
            # Emulate the sandbox account with this test process' existing UID.
            prefix = (
                "import os,pwd,types\n"
                f"pwd.getpwnam=lambda name: types.SimpleNamespace(pw_name=name,pw_gid={os.getgid()},pw_uid={os.getuid()})\n"
                "os.initgroups=lambda name,gid: None\n"
            )
            args = [sys.executable, "-c", prefix + "exec(" + repr(args[2]) + ")"]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return SimpleNamespace(
            exit_code=process.returncode, stdout=stdout.decode(), stderr=stderr.decode()
        )

    mock_e2b_module.files = SimpleNamespace(write=write)
    mock_e2b_module.commands.run = run
    content = bytes(range(256)) * 5000
    await backend.upload_file(session, "/workspace/input.bin", content, len(content))
    assert (workspace / "input.bin").read_bytes() == content
    outside = tmp_path / "outside"
    outside.write_bytes(b"private")
    (workspace / "linked.bin").symlink_to(outside)
    with pytest.raises(BoxError):
        await backend.upload_file(session, "/workspace/linked.bin", b"overwrite", 1024)
    assert outside.read_bytes() == b"private"


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["upload", "download"])
async def test_file_transfer_reconnect_uses_workspace_endpoints_and_routing(
    logger, mock_e2b_module, operation
):
    from e2b.connection_config import ConnectionConfig
    from langbot_plugin.box.models import E2BConnectionConfig

    config = E2BConnectionConfig(
        api_url="https://workspace-api.test",
        sandbox_url="https://workspace-sandbox.test",
        api_key="workspace-private-key",
        template="workspace-template",
    )
    selected = E2BSandboxBackend(logger, connection_config=config)
    await selected.initialize()
    session = await selected.start_session(
        BoxSpec(session_id="workspace-files", cmd="true")
    )

    class Stream:
        async def __aiter__(self):
            yield b"downloaded"

        async def aclose(self):
            pass

    mock_e2b_module.files = SimpleNamespace(
        write=mock.AsyncMock(), read=mock.AsyncMock(return_value=Stream())
    )
    if operation == "upload":
        await selected.upload_file(session, "/workspace/input.bin", b"input", 1024)
    else:
        assert (
            await selected.download_file(session, "/workspace/output.bin", 1024)
            == b"downloaded"
        )
    options = mock_e2b_module.connect.await_args.kwargs
    assert options == {
        "sandbox_id": session.backend_session_id,
        "request_timeout": 30,
        "api_key": config.api_key,
        "api_url": config.api_url,
        "sandbox_url": config.sandbox_url,
        "headers": {
            "E2b-Sandbox-Id": session.backend_session_id,
            "E2b-Sandbox-Port": str(ConnectionConfig.envd_port),
        },
    }


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["connect", "write", "command", "read"])
async def test_file_transfer_hides_custom_service_error_bodies(
    logger, mock_e2b_module, failure, caplog
):
    import traceback
    from langbot_plugin.box.models import E2BConnectionConfig

    secret = "workspace-secret-key"
    response_body = (
        f"service response echoed api_key={secret}, credential=private-provider-body"
    )
    selected = E2BSandboxBackend(
        logger,
        connection_config=E2BConnectionConfig(
            api_url="https://workspace-api.test",
            sandbox_url="https://workspace-sandbox.test",
            api_key=secret,
            template="base",
        ),
    )
    await selected.initialize()
    session = await selected.start_session(
        BoxSpec(session_id="private-files", cmd="true")
    )
    mock_e2b_module.files = SimpleNamespace(
        write=mock.AsyncMock(), read=mock.AsyncMock()
    )
    if failure == "connect":
        mock_e2b_module.connect.side_effect = RuntimeError(response_body)
    elif failure == "write":
        mock_e2b_module.files.write.side_effect = RuntimeError(response_body)
    elif failure == "command":
        mock_e2b_module.commands.run.return_value = SimpleNamespace(
            exit_code=1, stdout="", stderr=response_body
        )
    else:
        mock_e2b_module.files.read.side_effect = RuntimeError(response_body)
    with pytest.raises(BoxError) as caught:
        if failure == "read":
            await selected.download_file(session, "/workspace/report.bin", 1024)
        else:
            await selected.upload_file(session, "/workspace/input.bin", b"input", 1024)
    diagnostic = "".join(traceback.format_exception(caught.value)) + caplog.text
    assert secret not in diagnostic
    assert "private-provider-body" not in diagnostic


@pytest.mark.anyio
async def test_cancelled_file_transfer_logs_only_safe_custom_service_error(
    logger, mock_e2b_module, caplog
):
    from langbot_plugin.box.models import E2BConnectionConfig

    secret = "cancelled-workspace-secret"
    selected = E2BSandboxBackend(
        logger,
        connection_config=E2BConnectionConfig(
            api_url="https://workspace-api.test",
            sandbox_url="https://workspace-sandbox.test",
            api_key=secret,
            template="base",
        ),
    )
    await selected.initialize()
    session = await selected.start_session(
        BoxSpec(session_id="private-cancel", cmd="true")
    )
    started, finish = asyncio.Event(), asyncio.Event()

    async def write(*args, **kwargs):
        started.set()
        await finish.wait()
        raise RuntimeError(f"{secret}: private-provider-body")

    mock_e2b_module.files = SimpleNamespace(write=write)
    upload = asyncio.create_task(
        selected.upload_file(session, "/workspace/input.bin", b"input", 1024)
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        upload.cancel()
        await asyncio.sleep(0)
        assert not upload.done()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(upload, timeout=1)
    finally:
        finish.set()
        await asyncio.gather(upload, return_exceptions=True)
    assert "Cancelled E2B file transfer failed during completion" in caplog.text
    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text
    assert "private-provider-body" not in caplog.text
