import asyncio
import json
import os
import subprocess
import sys

import pytest

from langbot_plugin.runtime.io.connections.stdio import StdioConnection
from langbot_plugin.runtime.plugin.worker_launcher import (
    PluginWorkerLauncher,
    PluginWorkerProcessController,
)


@pytest.mark.parametrize(
    "noise", ["发起者ID".encode("gbk"), b"{broken}", b"ordinary log", b"[]"]
)
@pytest.mark.parametrize("chunked", [False, True])
async def test_stdio_discards_noise_and_keeps_next_message(noise, chunked, caplog):
    reader = asyncio.StreamReader()
    message = '{"code": 0}'
    if chunked:
        reader.feed_data(
            json.dumps({"type": "chunk_start", "total_size": len(message)}).encode()
            + b"\n"
        )
    reader.feed_data(noise + b"\n")
    if chunked:
        reader.feed_data(
            json.dumps({"type": "chunk_data", "offset": 0, "data": message}).encode()
            + b"\n"
        )
        reader.feed_data(b'{"type": "chunk_end"}\n')
    else:
        reader.feed_data(message.encode() + b"\n")
    reader.feed_eof()
    assert await StdioConnection(reader, None).receive() == message
    assert "Skipping" in caplog.text


def test_windows_worker_environment_prints_unicode(monkeypatch):
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "gbk")
    env = PluginWorkerLauncher(platform="win32")._windows_worker_environment()
    result = subprocess.run(
        [sys.executable, "-c", "print('\\u2717 \\U0001f60e \\u4e2d\\u6587')"],
        env=env,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode("utf-8").strip() == "✗ 😎 中文"


async def test_websocket_worker_stdout_uses_stderr(capfd, tmp_path):
    controller = PluginWorkerProcessController(
        command=sys.executable,
        args=["-c", "print('worker diagnostic')"],
        env=os.environ.copy(),
        working_dir=str(tmp_path),
    )
    await controller.run(None)
    out, err = capfd.readouterr()
    assert out == ""
    assert "worker diagnostic" in err
