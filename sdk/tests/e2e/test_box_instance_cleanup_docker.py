import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import socket
import sys
import uuid

import aiohttp
import pytest
import websockets

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.models import BoxSpec
from langbot_plugin.box.security import BOX_INSTANCE_HEADER
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler


pytestmark = pytest.mark.skipif(
    os.environ.get("LANGBOT_TEST_DOCKER_CLEANUP") != "1",
    reason="Requires a local Docker daemon and alpine:3.22",
)


async def docker(*args):
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 40)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise RuntimeError(stderr.decode())
    return stdout.decode().strip()


def unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@asynccontextmanager
async def rpc(port, instance_id):
    async with websockets.connect(
        f"ws://127.0.0.1:{port}/rpc/ws",
        additional_headers={BOX_INSTANCE_HEADER: instance_id},
        proxy=None,
    ) as websocket:
        handler = Handler(WebSocketConnection(websocket))
        handler_task = asyncio.create_task(handler.run())
        client = ActionRPCBoxClient(logging.getLogger(__name__))
        client.set_handler(handler)
        try:
            yield client
        finally:
            await handler.close()
            await asyncio.gather(handler_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_restart_cleans_only_own_containers(tmp_path):
    prefix = "box-cleanup-test-" + uuid.uuid4().hex[:12]
    owner_a, owner_b = prefix + "-a", prefix + "-b"
    port_a, port_b = unused_port(), unused_port()
    while port_b == port_a:
        port_b = unused_port()
    processes = []
    log_files = []
    legacy_id = None

    async def start(owner, port):
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("LANGBOT_BOX_")
        }
        env["LANGBOT_BOX_CONFIG"] = json.dumps({"backend": "docker"})
        log_path = tmp_path / f"{owner}-{len(processes)}.log"
        log_file = log_path.open("wb")
        log_files.append(log_file)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "langbot_plugin.cli.__init__",
            "box",
            "--host",
            "127.0.0.1",
            "--ws-control-port",
            str(port),
            "--instance-id",
            owner,
            "--data-dir",
            str(tmp_path / owner),
            env=env,
            stdout=log_file,
            stderr=log_file,
        )
        processes.append(process)
        async with aiohttp.ClientSession() as session:
            for _attempt in range(300):
                if process.returncode is not None:
                    raise RuntimeError(log_path.read_text())
                try:
                    async with session.get(
                        f"http://127.0.0.1:{port}/healthz"
                    ) as response:
                        if response.status == 200:
                            return process
                except aiohttp.ClientError:
                    pass
                await asyncio.sleep(0.1)
        raise TimeoutError("Box runtime did not start")

    async def owned(owner):
        output = await docker(
            "ps", "-aq", "--filter", f"label=langbot.box.instance_id={owner}"
        )
        return output.splitlines() if output else []

    try:
        legacy_id = prefix + "-legacy"
        legacy_id = await docker(
            "run",
            "-d",
            "--network",
            "none",
            "--name",
            legacy_id,
            "--label",
            "langbot.box=true",
            "alpine:3.22",
            "sleep",
            "600",
        )
        process_a = await start(owner_a, port_a)
        await start(owner_b, port_b)
        context_a = ActionContext(
            instance_uuid=owner_a, workspace_uuid="workspace", placement_generation=1
        )
        context_b = ActionContext(
            instance_uuid=owner_b, workspace_uuid="workspace", placement_generation=1
        )
        spec = BoxSpec(session_id="session", image="alpine:3.22", workdir="/tmp")
        async with rpc(port_a, owner_a) as client_a, rpc(port_b, owner_b) as client_b:
            await client_a.create_session(spec, action_context=context_a)
            await client_b.create_session(spec, action_context=context_b)
            containers_a, containers_b = await owned(owner_a), await owned(owner_b)
            assert len(containers_a) == len(containers_b) == 1
            marker = spec.model_copy(
                update={"cmd": "echo surviving-session > /tmp/marker"}
            )
            assert (
                await client_b.execute(marker, action_context=context_b)
            ).exit_code == 0
            process_a.kill()
            await process_a.wait()
            assert await owned(owner_a) == containers_a
            await start(owner_a, port_a)
            assert await owned(owner_a) == []
            assert await owned(owner_b) == containers_b
            result = await client_b.execute(
                spec.model_copy(update={"cmd": "cat /tmp/marker"}),
                action_context=context_b,
            )
            assert result.exit_code == 0
            assert result.stdout.strip() == "surviving-session"
            assert (
                await docker("inspect", "-f", "{{.State.Running}}", legacy_id) == "true"
            )
            print(
                json.dumps(
                    {
                        "ports": [port_a, port_b],
                        "removed_a": containers_a,
                        "preserved_b": containers_b,
                        "b_rpc_stdout": result.stdout.strip(),
                        "legacy_preserved": True,
                    }
                )
            )
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await process.wait()
        for log_file in log_files:
            log_file.close()
        containers = await owned(owner_a) + await owned(owner_b)
        if legacy_id is not None:
            containers.append(legacy_id)
        if containers:
            await docker("rm", "-f", *containers)
