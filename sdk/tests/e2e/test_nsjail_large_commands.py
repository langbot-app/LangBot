"""Opt-in Linux acceptance: LANGBOT_REAL_BOX_TESTS=1 pytest this file."""

import asyncio
import base64
import json
import logging
import os
from pathlib import Path

import pytest

from langbot_plugin.box.models import BoxExecutionStatus, BoxSpec
from langbot_plugin.box.nsjail_backend import NsjailBackend

pytestmark = pytest.mark.skipif(
    os.environ.get("LANGBOT_REAL_BOX_TESTS") != "1",
    reason="requires real nsjail on Linux",
)


@pytest.fixture
async def jail(tmp_path):
    backend = NsjailBackend(logging.getLogger(__name__), base_dir=str(tmp_path))
    spec = BoxSpec(session_id="large-command", network="off", timeout_sec=10)
    session = await backend.start_session(spec)
    try:
        yield backend, session, spec
    finally:
        await backend.stop_session(session)


@pytest.mark.asyncio
async def test_large_heredocs_preserve_contents_and_parallel_execution(jail):
    backend, session, spec = jail

    async def execute(index):
        # Core's attachment fallback encodes bytes inside a base64 JSON manifest.
        payload = bytes(range(256)) * 1024
        manifest = base64.b64encode(
            json.dumps({"b64": base64.b64encode(payload).decode()}).encode()
        ).decode()
        command = (
            "python3 - <<'LBPY'\nimport base64, json\n"
            f"data = base64.b64decode(json.loads(base64.b64decode('{manifest}'))['b64'])\n"
            f"open('attachment-{index}.bin', 'wb').write(data)\n"
            "print(len(data))\nLBPY"
        )
        result = await backend.exec(session, spec.model_copy(update={"cmd": command}))
        assert result.ok, result.stderr
        assert result.stdout.strip() == str(len(payload))
        assert (
            Path(session.backend_session_id) / "workspace" / f"attachment-{index}.bin"
        ).read_bytes() == payload

    await asyncio.gather(execute(1), execute(2))
    assert not list(Path(session.backend_session_id).glob("tmp/.langbot-exec-*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["failure", "timeout", "cancel"])
async def test_large_command_cleans_script_on_exit(jail, outcome):
    backend, session, spec = jail
    command = (
        "#" + "x" * 150000 + "\n" + ("exit 7" if outcome == "failure" else "sleep 30")
    )
    task = asyncio.create_task(
        backend.exec(
            session, spec.model_copy(update={"cmd": command, "timeout_sec": 1})
        )
    )
    if outcome == "cancel":
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        if outcome == "timeout":
            assert result.status == BoxExecutionStatus.TIMED_OUT
        else:
            assert result.exit_code == 7
    assert not list(Path(session.backend_session_id).glob("tmp/.langbot-exec-*"))
