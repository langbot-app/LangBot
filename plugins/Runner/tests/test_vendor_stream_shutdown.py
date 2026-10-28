"""Regression: stuck vendor work must not pin asyncio shutdown or survive it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("plugin", ["dashscope-agent", "tbox-agent"])
@pytest.mark.parametrize("operation", ["timeout", "cancel"])
def test_stuck_vendor_stream_does_not_block_event_loop_shutdown(plugin, operation, tmp_path):
    worker = tmp_path / "stuck_vendor.py"
    worker.write_text(
        "import json, os, sys, time\n"
        "sys.stdin.readline()\n"
        'print(json.dumps({"item": {"pid": os.getpid()}}), flush=True)\n'
        "time.sleep(60)\n"
    )
    code = f"""
import asyncio
import os
from pathlib import Path
from pkg.vendor_process import vendor_stream

async def main():
    stream = vendor_stream({{}}, timeout={0.5 if operation == "timeout" else 120}, worker=Path({str(worker)!r}))
    pid = (await anext(stream))["pid"]
    task = asyncio.create_task(anext(stream))
    if {operation == "cancel"}:
        await asyncio.sleep(0.05)
        task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        assert {operation == "cancel"}
    except TimeoutError:
        assert {operation == "timeout"}
    else:
        raise AssertionError('stalled fixture unexpectedly yielded')
    await stream.aclose()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pass
    else:
        raise AssertionError('vendor child survived cleanup')

asyncio.run(main())
print('EXECUTOR_SHUTDOWN_OK')
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT / plugin, text=True, capture_output=True, timeout=3
        )
    except subprocess.TimeoutExpired:
        pytest.fail("Vendor stream prevented bounded asyncio.run shutdown")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "EXECUTOR_SHUTDOWN_OK" in result.stdout
