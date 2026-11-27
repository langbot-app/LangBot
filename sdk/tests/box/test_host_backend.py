from __future__ import annotations

import asyncio
import logging
import os
import shlex
import signal

import pytest

from langbot_plugin.box.host_backend import HostProcessBackend
from langbot_plugin.box.models import (
    BoxExecutionStatus,
    BoxManagedProcessSpec,
    BoxMountSpec,
    BoxSpec,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="host backend is POSIX-only")


@pytest.fixture
def backend() -> HostProcessBackend:
    return HostProcessBackend(logging.getLogger("test.box.host"))


def _spec(tmp_path, *, cmd: str = "true", **changes) -> BoxSpec:
    values = {
        "session_id": "host-test",
        "cmd": cmd,
        "host_path": str(tmp_path),
        "read_only_rootfs": False,
    }
    values.update(changes)
    return BoxSpec(**values)


@pytest.mark.anyio
async def test_host_backend_exec_maps_workspace_paths(backend, tmp_path):
    spec = _spec(
        tmp_path,
        cmd="printf host-ok > /workspace/result.txt && cat /workspace/result.txt",
    )
    session = await backend.start_session(spec)
    try:
        result = await backend.exec(session, spec)
    finally:
        await backend.stop_session(session)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "host-ok"
    assert (tmp_path / "result.txt").read_text() == "host-ok"


@pytest.mark.anyio
async def test_host_backend_preserves_exit_code_and_stderr(backend, tmp_path):
    spec = _spec(
        tmp_path,
        cmd="printf host-out; printf host-error >&2; exit 7",
    )
    session = await backend.start_session(spec)
    try:
        result = await backend.exec(session, spec)
    finally:
        await backend.stop_session(session)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 7
    assert result.stdout == "host-out"
    assert result.stderr == "host-error"


@pytest.mark.anyio
async def test_host_backend_maps_extra_mounts_before_workspace(backend, tmp_path):
    workspace = tmp_path / "workspace"
    skill = tmp_path / "skill"
    workspace.mkdir()
    skill.mkdir()
    (skill / "value.txt").write_text("skill-ok")
    spec = _spec(
        workspace,
        cmd="cat /workspace/.skills/demo/value.txt",
        extra_mounts=[
            BoxMountSpec(
                host_path=str(skill),
                mount_path="/workspace/.skills/demo",
                mode="ro",
            )
        ],
    )
    session = await backend.start_session(spec)
    try:
        result = await backend.exec(session, spec)
    finally:
        await backend.stop_session(session)

    assert result.exit_code == 0
    assert result.stdout == "skill-ok"


@pytest.mark.anyio
async def test_host_backend_uses_minimal_environment(backend, tmp_path, monkeypatch):
    monkeypatch.setenv("LANGBOT_BOX_CONTROL_TOKEN", "must-not-leak")
    spec = _spec(
        tmp_path,
        cmd='[ -z "${LANGBOT_BOX_CONTROL_TOKEN+x}" ] && printf %s "$VISIBLE"',
        env={"VISIBLE": "provided"},
    )
    session = await backend.start_session(spec)
    try:
        result = await backend.exec(session, spec)
    finally:
        await backend.stop_session(session)

    assert result.exit_code == 0
    assert result.stdout == "provided"


@pytest.mark.anyio
async def test_host_backend_timeout_kills_process_group(backend, tmp_path):
    spec = _spec(
        tmp_path,
        cmd="sh -c 'sleep 30 & child=$!; printf %s \"$child\" > child.pid; wait'",
        timeout_sec=1,
    )
    session = await backend.start_session(spec)
    try:
        result = await backend.exec(session, spec)
        child_pid = int((tmp_path / "child.pid").read_text())
        for _ in range(20):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("timed-out host command left a child process running")
    finally:
        await backend.stop_session(session)

    assert result.status == BoxExecutionStatus.TIMED_OUT
    assert result.exit_code is None


@pytest.mark.anyio
async def test_host_backend_cancellation_kills_process_group(backend, tmp_path):
    spec = _spec(
        tmp_path,
        cmd="sh -c 'sleep 30 & child=$!; printf %s \"$child\" > child.pid; wait'",
    )
    session = await backend.start_session(spec)
    task = asyncio.create_task(backend.exec(session, spec))
    try:
        for _ in range(100):
            if (tmp_path / "child.pid").exists():
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("host command did not start its child process")

        child_pid = int((tmp_path / "child.pid").read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        for _ in range(20):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("cancelled host command left a child process running")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await backend.stop_session(session)


@pytest.mark.anyio
async def test_host_backend_managed_process_maps_cwd_and_args(backend, tmp_path):
    spec = _spec(tmp_path)
    session = await backend.start_session(spec)
    try:
        process = await backend.start_managed_process(
            session,
            BoxManagedProcessSpec(
                command="sh",
                args=["-c", "pwd; printf managed-ok > /workspace/managed.txt"],
                cwd="/workspace",
            ),
        )
        stdout = await process.stdout.read()
        assert await process.wait() == 0
    finally:
        await backend.stop_session(session)

    assert stdout.decode().strip() == str(tmp_path)
    assert (tmp_path / "managed.txt").read_text() == "managed-ok"


@pytest.mark.anyio
async def test_host_backend_reports_no_isolation(backend):
    readiness = await backend.get_readiness(strict=True)

    assert readiness["available"] is True
    assert readiness["unsafe_direct_execution"] is True
    assert readiness["namespace_isolation"] is False
    assert readiness["mount_isolation"] is False
    assert readiness["network_isolation"] is False
    assert readiness["cgroup_v2"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("trigger", ["timeout", "cancel"])
@pytest.mark.parametrize("topology", ["closed_output", "exited_parent"])
async def test_host_backend_kills_sigterm_resistant_descendants(
    backend, tmp_path, trigger, topology
):
    child_script = (
        "trap '' TERM\n"
        + ("exec >/dev/null 2>&1\n" if topology == "closed_output" else "")
        + 'printf %s "$$" > child.pid\nexec sleep 30'
    )
    command = (
        "printf before-timeout; printf before-timeout-error >&2\n"
        + 'printf %s "$$" > parent.pid\n'
        + f"sh -c {shlex.quote(child_script)} &\n"
        + "while [ ! -s child.pid ]; do sleep 0.01; done\n"
        + ("exit 0" if topology == "exited_parent" else "wait")
    )
    spec = _spec(tmp_path, cmd=command, timeout_sec=1 if trigger == "timeout" else 30)
    session = await backend.start_session(spec)
    task = asyncio.create_task(backend.exec(session, spec))
    parent_pid = None
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5
        pid_file = tmp_path / "child.pid"
        while not pid_file.exists() or not pid_file.read_text().strip():
            assert loop.time() < deadline, "child did not become ready"
            await asyncio.sleep(0.01)
        child_pid = int(pid_file.read_text())
        parent_pid = int((tmp_path / "parent.pid").read_text())
        assert os.getpgid(child_pid) == parent_pid

        # Exercise cancellation only after the parent has already been reaped.
        if topology == "exited_parent":
            while True:
                try:
                    os.kill(parent_pid, 0)
                except ProcessLookupError:
                    break
                assert loop.time() < deadline, "parent shell did not exit"
                await asyncio.sleep(0.01)

        if trigger == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), timeout=6)
        else:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=6)
            assert result.status == BoxExecutionStatus.TIMED_OUT
            assert result.stdout == "before-timeout"
            assert result.stderr == "before-timeout-error"

        deadline = loop.time() + 1
        while True:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            assert loop.time() < deadline, "SIGTERM-resistant child survived cleanup"
            await asyncio.sleep(0.01)
    finally:
        # A failing regression must not leave a live descendant in the runner.
        if parent_pid is None:
            pid_file = tmp_path / "parent.pid"
            if pid_file.exists() and pid_file.read_text().strip():
                parent_pid = int(pid_file.read_text())
        if parent_pid is not None:
            try:
                os.killpg(parent_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await backend.stop_session(session)
