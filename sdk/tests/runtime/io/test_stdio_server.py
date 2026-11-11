from __future__ import annotations

import asyncio
import io
import sys

import pytest

from langbot_plugin.runtime.io.controllers.stdio import server


class _TextStream:
    def __init__(self, buffer: io.BytesIO):
        self.buffer = buffer


async def test_windows_stdio_uses_threaded_binary_streams(monkeypatch):
    stdin_buffer = io.BytesIO(b"request\n")
    stdout_buffer = io.BytesIO()
    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(server.sys, "stdin", _TextStream(stdin_buffer))
    monkeypatch.setattr(server.sys, "stdout", _TextStream(stdout_buffer))

    reader, writer = await server.connect_stdin_stdout()

    assert await reader.readline() == b"request\n"
    writer.write(b"response\n")
    await writer.drain()
    assert stdout_buffer.getvalue() == b"response\n"

    writer.close()
    assert writer.is_closing() is True
    await writer.wait_closed()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows stdio handle behavior")
async def test_windows_stdio_works_in_redirected_subprocess():
    child_code = r"""
import asyncio
from langbot_plugin.runtime.io.controllers.stdio.server import connect_stdin_stdout

async def main():
    _, writer = await connect_stdin_stdout()
    writer.write(b"READY\n")
    await writer.drain()

asyncio.run(main())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        child_code,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)

    assert process.returncode == 0, stderr.decode(errors="replace")
    assert stdout == b"READY\n"
