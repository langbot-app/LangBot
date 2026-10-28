"""Native process fixtures use Python, not vendor CLI credentials/binaries."""

import asyncio
import contextlib
import importlib.util
import os
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("CODING_RUNNER_SOURCE_ROOT") or Path(__file__).resolve().parents[1])
FOLDERS = ("acp-agent-runner", "claude-code-agent", "codex-agent")


def load_plugin(folder, relative=None):
    old = {n: m for n, m in sys.modules.items() if n == "pkg" or n.startswith("pkg.")}
    for name in old:
        del sys.modules[name]
    sys.path.insert(0, str(ROOT / folder))
    try:
        relative = relative or ("components/runner/default.py" if folder == FOLDERS[0] else "pkg/native_cli.py")
        spec = importlib.util.spec_from_file_location(folder.replace("-", "_"), ROOT / folder / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules = {n: m for n, m in sys.modules.items() if n == "pkg" or n.startswith("pkg.")}
        return module, modules
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "pkg" or name.startswith("pkg."):
                del sys.modules[name]
        sys.modules.update(old)


def live(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_native_cancel_awaits_child_and_grandchild_exit(folder, tmp_path):
    module, modules = load_plugin(folder)
    pids = tmp_path / "pids"
    code = (
        "import os,subprocess,sys,time,signal; "
        "child=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)']); "
        f"open({str(pids)!r},'w').write(str(os.getpid())+' '+str(child.pid)); "
        "time.sleep(60)"
    )
    if folder == FOLDERS[0]:
        client = modules["pkg.acp_client"].AcpStdioClient(command=sys.executable, args=["-c", code], cwd=str(tmp_path))

        async def run():
            async with client:
                await asyncio.sleep(60)
    else:

        async def run():
            kwargs = dict(cwd=str(tmp_path), env=dict(os.environ), timeout=60, streaming=True)
            if folder == FOLDERS[1]:
                kwargs["expected_session_id"] = ""
            else:
                kwargs.update(resume_session_id="", prompt="fixture", agent_cwd=str(tmp_path))
            async for _ in module._run_cli_process_events(sys.executable, ["-c", code], **kwargs):
                pass

    task = asyncio.create_task(run())
    ids = []
    try:
        async with asyncio.timeout(4):
            while not pids.exists():
                await asyncio.sleep(0.01)
        ids = list(map(int, pids.read_text().split()))
        assert all(live(pid) for pid in ids)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, 10)
        assert not any(live(pid) for pid in ids), "native child/process group still running after cancel"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for pid in ids:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize("folder", FOLDERS)
def test_shared_workspace_defaults_and_dedicated_preserved(folder, tmp_path, monkeypatch):
    module, modules = load_plugin(folder)
    cls = getattr(
        module,
        {
            "acp-agent-runner": "DefaultRunner",
            "claude-code-agent": "NativeClaudeCodeRunner",
            "codex-agent": "NativeCodexRunner",
        }[folder],
    )
    from langbot_plugin.api.entities.builtin.runner import (
        AgentEventContext,
        AgentInput,
        AgentResources,
        AgentRunState,
        AgentRuntimeContext,
        AgentTrigger,
        DeliveryContext,
        RunnerContext,
    )

    ctx = RunnerContext(
        run_id="same-run",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="same-event", event_type="message.received", source="test"),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="test"),
        resources=AgentResources(),
        state=AgentRunState(),
        runtime=AgentRuntimeContext(),
        config={"location": "local"},
    )
    runner = cls()
    runner.bind_runtime(plugin_runtime_handler=object(), plugin_config={}, plugin_identity="fixture")
    monkeypatch.delenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", raising=False)
    assert runner._validate_config(ctx)["workspace"] == os.getcwd()
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_PROFILE", "shared")
    support = modules.get("pkg.runtime_support")
    if support:
        monkeypatch.setattr(support, "SHARED_DATA_ROOT", tmp_path)
    config = runner._validate_config(ctx)
    assert config["workspace"] == str(tmp_path / "workspace")
    assert (tmp_path / "workspace").is_dir()


@pytest.mark.asyncio
async def test_codex_same_session_serialized_distinct_accounts_independent(tmp_path):
    _, modules = load_plugin("codex-agent")
    support = modules.get("pkg.runtime_support")
    assert support is not None, "missing session serialization"
    entered = []
    release = asyncio.Event()

    async def first():
        async with support.session_guard(str(tmp_path / "account-A"), "session-1"):
            entered.append("first")
            await release.wait()

    async def second(home):
        async with support.session_guard(str(home), "session-1"):
            entered.append(str(home.name))

    a = asyncio.create_task(first())
    await asyncio.sleep(0)
    b = asyncio.create_task(second(tmp_path / "account-A"))
    c = asyncio.create_task(second(tmp_path / "account-B"))
    await asyncio.sleep(0.1)
    try:
        assert entered == ["first", "account-B"]
        release.set()
        await asyncio.gather(a, b, c)
        assert entered[-1] == "account-A"
    finally:
        release.set()
        await asyncio.gather(a, b, c, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_bundled_daemon_ack_only_after_native_group_exit(folder, tmp_path):
    module, modules = load_plugin(folder, "daemon.py" if folder == FOLDERS[0] else None)
    relay = modules["pkg.daemon_relay"]
    cls = getattr(
        module,
        {
            "acp-agent-runner": "RunnerDaemon",
            "claude-code-agent": "NativeClaudeCodeDaemon",
            "codex-agent": "NativeCodexDaemon",
        }[folder],
    )
    marker = tmp_path / "child"
    code = "import os,time; open(" + repr(str(marker)) + ",'w').write(str(os.getpid())); time.sleep(60)"
    config = dict(
        command=[sys.executable, "-c", code],
        args=[],
        acp_command=[sys.executable, "-c", code],
        workspace=str(tmp_path),
        langbot_assets_enabled=False,
        env={"CODEX_HOME": str(tmp_path / "auth")},
    )
    hub = relay.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token="fixture")
    client = cls(url=hub.endpoint, daemon_id="native", token="fixture")
    serving = asyncio.create_task(client.run_forever())
    await hub.wait_for_daemon("native", 2)

    async def consume():
        return [
            x
            async for x in hub.run_job(
                daemon_id="native",
                payload=dict(config=config, prompt="fixture", prompt_text="fixture"),
                tools=None,
                timeout=30,
            )
        ]

    task = asyncio.create_task(consume())
    pid = None
    try:
        async with asyncio.timeout(5):
            while not marker.exists():
                await asyncio.sleep(0.01)
        pid = int(marker.read_text())
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()  # cancellation cannot interrupt the acknowledgement barrier
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 8)
        assert not live(pid)
        assert not hub._jobs
        assert not hub._fenced, "a cooperative bundled client must acknowledge cleanup"
    finally:
        serving.cancel()
        task.cancel()
        await asyncio.gather(serving, task, return_exceptions=True)
        if pid:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        await hub.stop()


def test_codex_auth_and_resume_continuity_with_distinct_account_homes(tmp_path):
    module, _ = load_plugin("codex-agent")
    homes = []
    for owner in ("A", "B"):
        account = tmp_path / owner
        account.mkdir()
        (account / "auth.json").write_text(owner)
        (account / "sessions").mkdir()
        (account / "sessions" / "resume.jsonl").write_text(owner)
        env, _ = module._prepare_local_codex_home(
            str(tmp_path / "project"), "same-session", {"CODEX_HOME": str(account)}, ""
        )
        homes.append(Path(env["CODEX_HOME"]))
        assert (homes[-1] / "auth.json").read_text() == owner
        assert (homes[-1] / "sessions" / "resume.jsonl").read_text() == owner
    assert homes[0] != homes[1]
    assert (homes[0] / "sessions").resolve() != (homes[1] / "sessions").resolve()


@pytest.mark.asyncio
@pytest.mark.parametrize("folder", FOLDERS)
async def test_same_installation_two_agent_configs_and_reconfiguration(folder, tmp_path):
    import json
    import socket

    import websockets
    from langbot_plugin.api.entities.builtin.runner import (
        AgentEventContext,
        AgentInput,
        AgentResources,
        AgentRunState,
        AgentRuntimeContext,
        AgentTrigger,
        DeliveryContext,
        RunnerContext,
    )

    module, modules = load_plugin(folder)
    relay = modules["pkg.daemon_relay"]
    key = {"acp-agent-runner": "acp", "claude-code-agent": "claude-code", "codex-agent": "codex"}[folder]
    cls = getattr(
        module,
        {
            "acp-agent-runner": "DefaultRunner",
            "claude-code-agent": "NativeClaudeCodeRunner",
            "codex-agent": "NativeCodexRunner",
        }[folder],
    )
    runner = cls()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    plugin_config = {"daemon-host": "127.0.0.1", "daemon-port": port, "daemon-token": "installation-fixture"}
    runner.bind_runtime(plugin_runtime_handler=object(), plugin_config=plugin_config, plugin_identity="fixture")
    hub = relay.get_agent_runtime_daemon_hub(key)
    await hub.start(host="127.0.0.1", port=port, token="installation-fixture")
    sockets = []
    tasks = []
    try:
        for name in ("agent-A", "agent-B"):
            ws = await websockets.connect(hub.endpoint)
            sockets.append(ws)
            await ws.send(
                json.dumps(
                    dict(type="daemon.hello", daemon_id=name, token="installation-fixture", protocol="coding-relay-v1")
                )
            )
            await ws.recv()
            ctx = RunnerContext(
                run_id=name,
                trigger=AgentTrigger(type="message.received"),
                event=AgentEventContext(event_id="event", event_type="message.received", source="test"),
                input=AgentInput(text="test"),
                delivery=DeliveryContext(surface="test"),
                resources=AgentResources(),
                state=AgentRunState(),
                runtime=AgentRuntimeContext(),
                config={
                    "location": "daemon",
                    "daemon-id": name,
                    "workspace": str(tmp_path / name),
                    "langbot-assets-enabled": False,
                    "env": {"ACCOUNT": name},
                },
            )
            config = runner._validate_config(ctx)
            args = (ctx, config, name, "") + ((False,) if key == "claude-code" else ())

            async def consume(args):
                return [e async for e in runner._run_daemon(*args)]

            tasks.append(asyncio.create_task(consume(args)))
        for index, ws in enumerate(sockets):
            frame = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert frame["payload"]["config"]["workspace"] == str(tmp_path / ("agent-A" if index == 0 else "agent-B"))
            await ws.send(
                json.dumps(
                    dict(
                        type="run.event",
                        job_id=frame["job_id"],
                        event=dict(type="run.completed", data=dict(finish_reason="stop")),
                    )
                )
            )
            await ws.send(json.dumps(dict(type="run.finished", job_id=frame["job_id"])))
        assert all(len(events) == 1 for events in await asyncio.gather(*tasks))
        runner.bind_runtime(
            plugin_runtime_handler=object(),
            plugin_config={**plugin_config, "daemon-token": "replacement"},
            plugin_identity="fixture",
        )
        config = runner._validate_config(ctx)
        args = (ctx, config, "test", "") + ((False,) if key == "claude-code" else ())
        with pytest.raises(relay.AgentRuntimeDaemonError, match="different config"):
            await consume(args)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for ws in sockets:
            await ws.close()
        await hub.stop()


@pytest.mark.asyncio
async def test_cleanup_os_failure_never_becomes_successful_ack(monkeypatch):
    _, modules = load_plugin("codex-agent")
    support = modules["pkg.runtime_support"]

    async def failure(process):
        raise PermissionError("fixture kill denied")

    monkeypatch.setattr(support, "_terminate", failure)
    with pytest.raises(support.ProcessCleanupUnconfirmed):
        await support.terminate_process_group(object())
