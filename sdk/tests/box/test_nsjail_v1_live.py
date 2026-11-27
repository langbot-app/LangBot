"""Opt-in kernel verification on a host with delegated v1 controllers."""

from __future__ import annotations

import logging
import os
import shlex

import pytest

from langbot_plugin.box.models import BoxSpec
from langbot_plugin.box.nsjail_backend import NsjailBackend

pytestmark = pytest.mark.skipif(
    os.getenv("LANGBOT_LIVE_WORKSPACE_BACKENDS") != "1",
    reason="requires a delegated Linux validation host",
)


@pytest.mark.asyncio
async def test_pid_limit_is_enforced_inside_jail_without_counting_host_uid(tmp_path):
    backend = NsjailBackend(
        logging.getLogger("nsjail-v1-live"), base_dir=str(tmp_path / "jails")
    )
    backend.configure(
        {"cgroup_v1_parent": os.environ["LANGBOT_NSJAIL_CGROUP_V1_PARENT"]}
    )
    assert await backend.probe_available()
    assert backend._cgroup_v1_available
    outside = tmp_path / "outside-marker"
    outside.write_text("must-not-be-visible")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    program = """
import errno
import subprocess
children = []
try:
    for _ in range(20):
        try:
            children.append(subprocess.Popen(['/bin/sleep', '5']))
        except OSError as exc:
            assert exc.errno == errno.EAGAIN, exc
            break
    assert 0 < len(children) < 8, len(children)
    print('PER_JAIL_PID_LIMIT_OK')
finally:
    for child in children:
        child.terminate()
    for child in children:
        child.wait()
"""
    spec = BoxSpec(
        session_id="pid-limit-live",
        host_path=str(workspace),
        pids_limit=8,
        timeout_sec=10,
        cmd=f"test ! -e {shlex.quote(str(outside))} && /usr/bin/python3 -c {shlex.quote(program)}",
    )
    session = await backend.start_session(spec)
    try:
        result = await backend.exec(session, spec)
        assert result.ok and result.stdout == "PER_JAIL_PID_LIMIT_OK", (
            result.model_dump()
        )
        print("PER_JAIL_PID_LIMIT_AND_HOST_FILE_ISOLATION_PASS")
    finally:
        await backend.stop_session(session)
