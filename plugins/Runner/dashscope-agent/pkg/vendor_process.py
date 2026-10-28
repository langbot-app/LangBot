"""Killable synchronous vendor isolation with bounded pipe backpressure.

No executor threads, inherited provider secrets or queues. A worker is reaped
before cancellation/timeout/early-close returns. Host limits concurrent runs.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

MAX_FRAME = 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024


async def vendor_stream(payload, *, timeout, worker=None):
    worker = worker or Path(__file__).with_name("vendor_worker.py")
    payload = dict(payload, import_paths=sys.path)
    encoded = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
    if len(encoded) > 16 * 1024 * 1024:
        raise ValueError("Vendor request exceeds the runtime limit")
    # A private parent-owned directory survives a killed upload only until reap.
    with tempfile.TemporaryDirectory(prefix="langbot-vendor-") as temp:
        env = {"PATH": os.defpath, "TMPDIR": temp, "HOME": temp, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                sys.executable,
                str(worker),
                cwd=temp,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=MAX_FRAME + 1,
            )
        )
        process = None
        try:
            end = asyncio.get_running_loop().time() + timeout

            async def wait(operation):
                remaining = end - asyncio.get_running_loop().time()
                async with asyncio.timeout(max(0, remaining)):
                    return await operation

            process = await wait(asyncio.shield(spawn))
            process.stdin.write(encoded)
            await wait(process.stdin.drain())
            process.stdin.close()
            total = 0
            while True:
                line = await wait(process.stdout.readline())
                if not line:
                    if await wait(process.wait()) != 0:
                        raise RuntimeError("Vendor worker failed")
                    break
                total += len(line)
                if len(line) > MAX_FRAME or total > MAX_TOTAL:
                    raise ValueError("Vendor response exceeds the runtime limit")
                frame = json.loads(line)
                if "error" in frame:
                    if frame["error"] == "timeout":
                        raise TimeoutError("Vendor timed out")
                    raise RuntimeError("Vendor request failed")
                yield frame["item"]

        finally:

            async def reap():
                proc = process or await spawn
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                # Drain after kill: Process.wait alone can wait for a full pipe.
                if proc.stdout:
                    while await proc.stdout.read(65536):
                        pass
                await proc.wait()

            cleanup = asyncio.create_task(reap())
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup.result()
            if cancelled:
                raise asyncio.CancelledError
