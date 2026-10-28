"""Real b5 + loopback transport regressions (no vendor or nsjail claim)."""

import asyncio
import contextlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
import websockets
from langbot_plugin.api.agent_tools import daemon as stock

ROOT = Path(os.environ.get("CODING_RUNNER_SOURCE_ROOT") or Path(__file__).resolve().parents[1])
FOLDERS = ("acp-agent-runner", "claude-code-agent", "codex-agent")
TOKEN = "test-only-installation-token-8f69c142049db2bc"


def load(folder):
    path = ROOT / folder / "pkg/daemon_relay.py"
    if not path.exists():
        return stock  # RED runs exercise the actual pre-fix implementation.
    spec = importlib.util.spec_from_file_location("relay_" + folder, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def connect(hub, name, *, token=TOKEN, protocol="coding-relay-v1"):
    ws = await websockets.connect(hub.endpoint)
    await ws.send(json.dumps(dict(type="daemon.hello", daemon_id=name, token=token, protocol=protocol)))
    try:
        reply = json.loads(await asyncio.wait_for(ws.recv(), 2))
        assert reply["type"] == "daemon.ready"
        return ws
    except BaseException:
        await ws.close()
        raise


async def collect(stream):
    return [item async for item in stream]


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_serialized_start_and_conflicts(folder, monkeypatch):
    m = load(folder)
    hub = m.AgentRuntimeDaemonHub()
    servers = []
    original = m.websockets.serve

    async def counted(*args, **kwargs):
        server = await original(*args, **kwargs)
        servers.append(server)
        return server

    monkeypatch.setattr(m.websockets, "serve", counted)
    try:
        await asyncio.gather(*(hub.start(host="127.0.0.1", port=0, token=TOKEN) for _ in range(8)))
        with pytest.raises(m.AgentRuntimeDaemonError, match="config|started"):
            await hub.start(host="127.0.0.1", port=0, token=TOKEN + "changed")
        assert len(servers) == 1, "concurrent startup leaked extra listeners"
    finally:
        await hub.stop()
        for server in servers:
            server.close()
            await server.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_shared_auth_and_old_client_denied(folder, monkeypatch):
    m = load(folder)
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", "shared")
    for token in ("", "short", "a" * 40):
        hub = m.AgentRuntimeDaemonHub()
        try:
            with pytest.raises(m.AgentRuntimeDaemonError, match="token"):
                await hub.start(host="127.0.0.1", port=0, token=token)
        finally:
            await hub.stop()
    hub = m.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    try:
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            await connect(hub, "old", protocol="")
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            await connect(hub, "wrong", token="wrong")
    finally:
        await hub.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_sender_ownership_events_finish_mcp_and_replacement(folder):
    m = load(folder)
    hub = m.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    owner = await connect(hub, "owner")
    attacker = await connect(hub, "attacker")
    calls = []

    async def mcp(tools, payload):
        calls.append(payload)
        return {"ok": True}

    old = m.handle_agent_runtime_mcp_payload
    m.handle_agent_runtime_mcp_payload = mcp
    task = asyncio.create_task(collect(hub.run_job(daemon_id="owner", payload={}, tools=object(), timeout=10)))
    try:
        frame = json.loads(await owner.recv())
        job = frame["job_id"]
        for msg in [
            dict(type="run.event", event={"type": "injected"}),
            dict(type="run.finished"),
            dict(type="mcp.request", request_id="bad", payload={}),
        ]:
            await attacker.send(json.dumps(dict(job_id=job, **msg)))
        await attacker.send(json.dumps({"type": "daemon.ping"}))
        while json.loads(await attacker.recv())["type"] != "daemon.pong":
            pass
        assert not task.done(), "foreign finished frame ended the run"
        assert not calls, "foreign MCP sender acquired run tools"
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            await connect(hub, "owner")
        await owner.send(json.dumps(dict(type="run.event", job_id=job, event={"type": "legitimate"})))
        await owner.send(json.dumps(dict(type="run.finished", job_id=job)))
        assert await task == [{"type": "legitimate"}]
    finally:
        m.handle_agent_runtime_mcp_payload = old
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        await owner.close()
        await attacker.close()
        await hub.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
@pytest.mark.parametrize("action", ["cancel", "disconnect", "timeout"])
async def test_real_standard_client_cancels_and_reaps_child(folder, action, tmp_path):
    m = load(folder)
    child_started = asyncio.Event()
    cleaned = asyncio.Event()
    processes = []

    class Client(m.AgentRuntimeDaemonClient):
        async def run_job(self, job_id, payload):
            p = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "import time; time.sleep(60)", start_new_session=True
            )
            processes.append(p)
            child_started.set()
            try:
                await p.wait()
            finally:
                with contextlib.suppress(ProcessLookupError):
                    p.kill()
                await p.wait()
                cleaned.set()

    hub = m.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    client = Client(url=hub.endpoint, daemon_id="worker", token=TOKEN, reconnect_delay=60)
    serving = asyncio.create_task(client.run_forever())
    await hub.wait_for_daemon("worker", 3)
    run = asyncio.create_task(
        collect(hub.run_job(daemon_id="worker", payload={}, tools=None, timeout=0.2 if action == "timeout" else 30))
    )
    try:
        await asyncio.wait_for(child_started.wait(), 3)
        if action == "cancel":
            run.cancel()
        elif action == "disconnect":
            await client.websocket.close()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(run, 4)
        if action == "disconnect":
            assert "worker" in hub._fenced  # No socket remains to acknowledge cleanup.
            await asyncio.wait_for(cleaned.wait(), 2)
        assert cleaned.is_set(), "run returned without remote child cleanup"
        assert processes[0].returncode is not None
        if action == "cancel":
            assert not hub._jobs
    finally:
        serving.cancel()
        run.cancel()
        await asyncio.gather(serving, run, return_exceptions=True)
        for p in processes:
            if p.returncode is None:
                p.kill()
                await p.wait()
        await hub.stop()


@pytest.mark.asyncio
async def test_unacknowledged_cancel_fences_target_and_revokes_tools():
    m = load(FOLDERS[0])
    hub = m.AgentRuntimeDaemonHub()
    hub.cancel_timeout = 0.1
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    ws = await connect(hub, "uncooperative")
    run = asyncio.create_task(collect(hub.run_job(daemon_id="uncooperative", payload={}, tools=object(), timeout=30)))
    try:
        await ws.recv()
        run.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run
        with pytest.raises(m.AgentRuntimeDaemonError, match="fenced"):
            await collect(hub.run_job(daemon_id="uncooperative", payload={}, tools=None, timeout=1))
        assert not hub._jobs
    finally:
        await ws.close()
        await hub.stop()


def test_relay_copies_identical():
    paths = [ROOT / folder / "pkg/daemon_relay.py" for folder in FOLDERS]
    assert all(p.exists() for p in paths)
    assert len({p.read_bytes() for p in paths}) == 1


@pytest.mark.asyncio
async def test_unresolved_fence_survives_hub_recreation(tmp_path):
    m = load(FOLDERS[0])
    hub = m.AgentRuntimeDaemonHub(state_dir=tmp_path)
    hub.cancel_timeout = 0.05
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    ws = await connect(hub, "lost")
    run = asyncio.create_task(collect(hub.run_job(daemon_id="lost", payload={}, tools=None, timeout=30)))
    await ws.recv()
    run.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run
    await ws.close()
    await hub.stop()
    replacement = m.AgentRuntimeDaemonHub(state_dir=tmp_path)
    await replacement.start(host="127.0.0.1", port=0, token=TOKEN)
    try:
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            await connect(replacement, "lost")
    finally:
        await replacement.stop()


@pytest.mark.asyncio
async def test_client_cleanup_failure_refuses_reconnect():
    m = load(FOLDERS[0])

    class Unconfirmed(BaseException):
        pass

    class Client(m.AgentRuntimeDaemonClient):
        async def run_job(self, job_id, payload):
            raise Unconfirmed("fixture cleanup failed")

    hub = m.AgentRuntimeDaemonHub()
    hub.cancel_timeout = 0.05
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    c = Client(url=hub.endpoint, daemon_id="bad-cleanup", token=TOKEN, reconnect_delay=0.01)
    serving = asyncio.create_task(c.run_forever())
    await hub.wait_for_daemon("bad-cleanup", 2)
    run = asyncio.create_task(collect(hub.run_job(daemon_id="bad-cleanup", payload={}, tools=None, timeout=0.2)))
    try:
        with contextlib.suppress(TimeoutError):
            await run
        await asyncio.sleep(0.1)
        assert serving.done(), "failed cleanup left the client available for more jobs"
        assert isinstance(serving.exception(), RuntimeError)
        assert "bad-cleanup" in hub._fenced
    finally:
        serving.cancel()
        await asyncio.gather(serving, run, return_exceptions=True)
        await hub.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_two_separate_installation_processes_shared_network(folder, tmp_path, monkeypatch):
    monkeypatch.setenv("FOREIGN_HOST_SECRET", "synthetic-not-a-real-host-secret")
    workers = []
    infos = []
    tokens = [TOKEN + "A", TOKEN + "B"]

    async def command(worker, cmd):
        worker.stdin.write((json.dumps(dict(command=cmd)) + "\n").encode())
        await worker.stdin.drain()
        return json.loads(await asyncio.wait_for(worker.stdout.readline(), 4))

    try:
        for index in range(2):
            state = tmp_path / str(index)
            for child in ("home", "tmp", "data"):
                (state / child).mkdir(parents=True)
            # Match real worker construction's empty inherited environment. This
            # verifies separate processes and network, not kernel mount isolation.
            env = dict(
                HOME=str(state / "home"),
                TMPDIR=str(state / "tmp"),
                PYTHONUNBUFFERED="1",
                PYTHONDONTWRITEBYTECODE="1",
                LANGBOT_PLUGIN_RUNTIME_PROFILE="shared",
            )
            worker = await asyncio.create_subprocess_exec(
                sys.executable,
                str(Path(__file__).with_name("coding_process_worker.py")),
                str(ROOT / folder),
                str(state / "data"),
                tokens[index],
                env=env,
                cwd=str(state / "data"),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            workers.append(worker)
            infos.append(json.loads(await asyncio.wait_for(worker.stdout.readline(), 5)))
        assert infos[0]["pid"] != infos[1]["pid"]
        assert infos[0]["home"] != infos[1]["home"] and infos[0]["tmp"] != infos[1]["tmp"]
        assert all(i["foreign_env"] is None for i in infos)
        # Opposite installation tokens fail on the actual other listener.
        for index in range(2):
            ws = await websockets.connect(infos[index]["endpoint"])
            await ws.send(
                json.dumps(
                    dict(type="daemon.hello", daemon_id="attacker", token=tokens[1 - index], protocol="coding-relay-v1")
                )
            )
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await ws.recv()
        starts = await asyncio.gather(*(command(w, "run") for w in workers))
        assert starts[0]["child_pid"] != starts[1]["child_pid"]
        assert await command(workers[0], "cancel") == dict(cleaned=True, fenced=False)
        assert await command(workers[1], "status") == dict(running=True)
        assert await command(workers[1], "cancel") == dict(cleaned=True, fenced=False)
    finally:
        for worker in workers:
            if worker.returncode is None:
                worker.stdin.write(b'{"command":"stop"}\n')
                await worker.stdin.drain()
                await asyncio.wait_for(worker.wait(), 5)
            assert worker.returncode == 0, (await worker.stderr.read()).decode()


@pytest.mark.asyncio
async def test_bind_conflict_is_actionable():
    m = load(FOLDERS[0])
    first = m.AgentRuntimeDaemonHub()
    second = m.AgentRuntimeDaemonHub()
    await first.start(host="127.0.0.1", port=0, token=TOKEN)
    try:
        port = int(first.endpoint.rsplit(":", 1)[1])
        with pytest.raises(m.AgentRuntimeDaemonError, match="unique daemon-port"):
            await second.start(host="127.0.0.1", port=port, token=TOKEN)
    finally:
        await first.stop()
        await second.stop()


@pytest.mark.asyncio
async def test_cancel_pending_refuses_target_reuse():
    m = load(FOLDERS[0])
    hub = m.AgentRuntimeDaemonHub()
    hub.cancel_timeout = 0.1
    await hub.start(host="127.0.0.1", port=0, token=TOKEN)
    ws = await connect(hub, "busy")
    task = asyncio.create_task(collect(hub.run_job(daemon_id="busy", payload={}, tools=None, timeout=10)))
    second = None
    try:
        await ws.recv()
        task.cancel()
        cancel = json.loads(await ws.recv())
        assert cancel["type"] == "run.cancel"
        second = asyncio.create_task(collect(hub.run_job(daemon_id="busy", payload={}, tools=None, timeout=0.01)))
        with pytest.raises(m.AgentRuntimeDaemonError, match="cancelling|fenced"):
            await second
    finally:
        task.cancel()
        if second is not None:
            second.cancel()
        await asyncio.gather(task, *([second] if second is not None else []), return_exceptions=True)
        await ws.close()
        await hub.stop()
