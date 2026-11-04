"""Unit tests for E2BSandboxBackend.

These tests do NOT require e2b package to be installed – they mock the E2B SDK
to verify parameter mapping, session lifecycle, and availability detection.
"""

from __future__ import annotations

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
        sandbox_id="sandbox-test-123", api_key="test-api-key"
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
async def test_exec_success(backend, mock_e2b_module):
    """exec runs command and returns result."""
    backend._api_key = "test-api-key"

    session = BoxSessionInfo(
        session_id="exec-sess",
        backend_name="e2b",
        backend_session_id="sandbox-123",
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
    mock_e2b_module.connect.assert_called_once()
    mock_e2b_module.commands.run.assert_called_once()

    # Verify command includes path adaptation
    run_kwargs = mock_e2b_module.commands.run.call_args.kwargs
    assert "/home/user/workspace" in run_kwargs["cmd"]


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


@pytest.mark.anyio
async def test_exec_does_not_upload_or_download_writable_workspace(
    backend, mock_e2b_module, tmp_path
):
    (tmp_path / "identity.txt").write_bytes(b"HOST_COPY")
    spec = BoxSpec(
        session_id="private-box",
        cmd="rm /workspace/identity.txt",
        host_path=str(tmp_path),
    )
    sandbox = mock_e2b_module
    sandbox.files = SimpleNamespace(
        write=mock.AsyncMock(), write_files=mock.AsyncMock(), list=mock.AsyncMock()
    )
    session = await backend.start_session(spec)
    await backend.exec(session, spec)
    assert "host-mount" not in sandbox.create.call_args.kwargs.get("metadata", {})
    sandbox.files.write.assert_not_awaited()
    sandbox.files.write_files.assert_not_awaited()
    sandbox.files.list.assert_not_awaited()
    assert (tmp_path / "identity.txt").read_bytes() == b"HOST_COPY"


@pytest.mark.anyio
async def test_read_only_mount_is_prepared_before_exec(
    backend, mock_e2b_module, tmp_path
):
    (tmp_path / "resource.txt").write_bytes(b"RESOURCE")
    spec = BoxSpec(
        session_id="private-box",
        cmd="true",
        extra_mounts=[
            BoxMountSpec(
                host_path=str(tmp_path),
                mount_path="/opt/resources",
                mode=BoxHostMountMode.READ_ONLY,
            )
        ],
    )
    backend._materialize_immutable_mount = mock.AsyncMock()
    session = await backend.start_session(spec)
    await backend.exec(session, spec)
    backend._materialize_immutable_mount.assert_awaited_once()


@pytest.mark.anyio
async def test_writable_extra_mount_requires_explicit_import(backend, mock_e2b_module):
    spec = BoxSpec(
        session_id="private-box",
        cmd="true",
        extra_mounts=[
            BoxMountSpec(
                host_path="/tmp/host-data",
                mount_path="/data",
                mode=BoxHostMountMode.READ_WRITE,
            )
        ],
    )
    session = await backend.start_session(spec)
    with pytest.raises(BoxError, match="explicitly import"):
        await backend.exec(session, spec)
    mock_e2b_module.commands.run.assert_not_awaited()


@pytest.mark.anyio
async def test_remote_workspace_quota_failure_blocks_command(backend, mock_e2b_module):
    spec = BoxSpec(session_id="private-box", cmd="do-not-run", workspace_quota_mb=1)
    mock_e2b_module.commands.run.return_value.exit_code = 1
    mock_e2b_module.commands.run.return_value.stderr = "workspace quota exceeded"
    session = await backend.start_session(spec)
    with pytest.raises(BoxError, match="workspace quota"):
        await backend.exec(session, spec)
    assert len(mock_e2b_module.commands.run.await_args_list) == 1
