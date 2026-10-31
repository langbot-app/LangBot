"""Separate-process fixture: real TCP/client/subprocess, NOT an nsjail emulator."""

import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from pkg.daemon_relay import AgentRuntimeDaemonClient, AgentRuntimeDaemonHub


async def main():
    state = Path(sys.argv[2])
    token = sys.argv[3]
    hub = AgentRuntimeDaemonHub(state_dir=state / "leases")
    await hub.start(host="127.0.0.1", port=0, token=token)
    processes = []

    class Client(AgentRuntimeDaemonClient):
        async def run_job(self, job_id, payload):
            p = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "import time; time.sleep(60)", start_new_session=True
            )
            processes.append(p)
            try:
                await self.emit_event(job_id, dict(type="fixture.started", data=dict(pid=p.pid)))
                await p.wait()
            finally:
                with contextlib.suppress(ProcessLookupError):
                    p.kill()
                await p.wait()

    client = Client(url=hub.endpoint, daemon_id="same-display", token=token)
    serving = asyncio.create_task(client.run_forever())
    await hub.wait_for_daemon("same-display", 2)
    task = None
    started = asyncio.Event()

    async def run():
        async for event in hub.run_job(
            daemon_id="same-display", payload=dict(run_id="same-conversation"), tools=None, timeout=30
        ):
            if event["type"] == "fixture.started":
                started.set()

    def emit(data):
        print(json.dumps(data), flush=True)

    emit(
        dict(
            endpoint=hub.endpoint,
            pid=os.getpid(),
            home=os.environ["HOME"],
            tmp=os.environ["TMPDIR"],
            foreign_env=os.getenv("FOREIGN_HOST_SECRET"),
        )
    )
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            command = json.loads(line)["command"]
            if command == "run":
                task = asyncio.create_task(run())
                await asyncio.wait_for(started.wait(), 2)
                emit(dict(started=True, child_pid=processes[-1].pid))
            elif command == "cancel":
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                emit(dict(cleaned=processes[-1].returncode is not None, fenced=bool(hub._fenced)))
            elif command == "status":
                emit(dict(running=processes[-1].returncode is None))
            elif command == "stop":
                break
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        serving.cancel()
        await asyncio.gather(serving, return_exceptions=True)
        await hub.stop()


asyncio.run(main())
