"""HISTORICAL RED reproducer, excluded from normal pytest discovery.

Preserved from 35f75ee; this is not an acceptance suite. Its same-interpreter
cross-installation, inherited worker-secret and shared Codex-account assertions
were overgeneralized. See topology-reassessment.md in the retained evidence.
The current replacement suites are test_coding_relay_v1.py and
 test_coding_native_lifecycle.py (no xfail). Explicitly running this historical
file reproduces the old model, not candidate certification results.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest
import websockets
from langbot_plugin.api.agent_tools import daemon
from langbot_plugin.api.definition.components.runner.runner import Runner
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
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    DependencyEnvironmentPreparationError,
    PluginDependencyEnvironmentStore,
)

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = (
    ("acp-agent-runner", "ACPAgentRunner", "0.1.12", "acp"),
    ("claude-code-agent", "ClaudeCodeAgent", "0.1.10", "claude-code"),
    ("codex-agent", "CodexAgent", "0.1.16", "codex"),
)
blocker = pytest.mark.xfail(
    os.environ.get("CODING_RUNNER_ENFORCE_SHARED_SAFETY") != "1",
    strict=True,
    raises=AssertionError,
    reason="BLOCKED: b5/current coding Runner lacks this safety contract",
)
admission_blocker = pytest.mark.xfail(
    os.environ.get("CODING_RUNNER_ENFORCE_SHARED_SAFETY") != "1",
    strict=True,
    raises=DependencyEnvironmentPreparationError,
    reason="BLOCKED: exact historical archive requires b3, Runtime provides b5",
)


def load_plugin(folder):
    """Keep SDK genuine; isolate only the plugins' colliding `pkg` modules."""
    old = {n: m for n, m in sys.modules.items() if n == "pkg" or n.startswith("pkg.")}
    for name in old:
        del sys.modules[name]
    sys.path.insert(0, str(ROOT / folder))
    try:
        relative = "components/runner/default.py" if folder == "acp-agent-runner" else "pkg/native_cli.py"
        spec = importlib.util.spec_from_file_location(folder.replace("-", "_"), ROOT / folder / relative)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls = getattr(
            module,
            {
                "acp-agent-runner": "DefaultRunner",
                "claude-code-agent": "NativeClaudeCodeRunner",
                "codex-agent": "NativeCodexRunner",
            }[folder],
        )
        return module, cls()
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "pkg" or name.startswith("pkg."):
                del sys.modules[name]
        sys.modules.update(old)


def context(run_id, config=None):
    return RunnerContext(
        run_id=run_id,
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="fixture-event", event_type="message.received", source="test"),
        input=AgentInput(text="synthetic prompt"),
        delivery=DeliveryContext(surface="test"),
        resources=AgentResources(),
        state=AgentRunState(),
        runtime=AgentRuntimeContext(metadata={"steering_enabled": False}),
        config=config or {},
    )


class NoHostCalls:
    async def call_action(self, *args, **kwargs):
        raise AssertionError("This local execution bypass did not need any Host grant")


async def connect(hub, daemon_id, token="fixture-A"):
    ws = await websockets.connect(hub.endpoint)
    await ws.send(json.dumps({"type": "daemon.hello", "daemon_id": daemon_id, "token": token}))
    assert json.loads(await asyncio.wait_for(ws.recv(), 2))["type"] == "daemon.ready"
    return ws


async def collect(stream):
    return [event async for event in stream]


@pytest.mark.asyncio
@pytest.mark.parametrize("folder,name,version,key", PLUGINS)
@blocker
async def test_conflicting_installation_token_cannot_route_to_existing_daemon(folder, name, version, key):
    """A run with config B must not reach the daemon authenticated with config A."""
    _, runner = load_plugin(folder)
    hub = daemon.get_agent_runtime_daemon_hub(key)
    assert not hub.is_running, "run this suite in an isolated interpreter"
    await hub.start(host="127.0.0.1", port=0, token="fixture-A")
    ws = await connect(hub, "same-display-id")
    runner.bind_runtime(
        plugin_runtime_handler=NoHostCalls(),
        plugin_config={
            "daemon-host": "127.0.0.1",
            "daemon-port": 1,
            "daemon-token": "fixture-B",
        },
        plugin_identity="langbot-team/" + name,
    )
    ctx = context(
        "run-B",
        {
            "location": "daemon",
            "daemon-id": "same-display-id",
            "workspace": "/fixture-B",
            "langbot-assets-enabled": False,
        },
    )
    config = runner._validate_config(ctx)
    assert config["daemon_hub"]["token"] == "fixture-B"
    args = (ctx, config, "only-B-prompt", "") + ((False,) if key == "claude-code" else ())
    task = asyncio.create_task(collect(runner._run_daemon(*args)))
    frame = None
    try:
        try:
            frame = json.loads(await asyncio.wait_for(ws.recv(), 1))
        except TimeoutError:
            pass
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await ws.close()
        await hub.stop()
    assert frame is None, "Foreign-config run reached A's authenticated connection: " + str(frame and frame["type"])


@pytest.mark.asyncio
async def test_hub_start_itself_rejects_conflicting_token():
    """Positive control: the runners skip the SDK's existing conflict check."""
    hub = daemon.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token="fixture-A")
    try:
        with pytest.raises(daemon.AgentRuntimeDaemonError, match="already started"):
            await hub.start(host="127.0.0.1", port=0, token="fixture-B")
    finally:
        await hub.stop()


@pytest.mark.asyncio
@blocker
async def test_daemon_cannot_inject_event_into_another_daemons_job():
    """Knowledge of a job ID is not authority; test genuine websocket dispatch."""
    hub = daemon.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token="fixture-A")
    a = await connect(hub, "A")
    b = await connect(hub, "B")
    stream = hub.run_job(daemon_id="A", payload={"run_id": "run-A"}, tools=None, timeout=3)
    task = asyncio.create_task(anext(stream))
    received = None
    try:
        frame = json.loads(await asyncio.wait_for(a.recv(), 2))
        await b.send(
            json.dumps(
                {
                    "type": "run.event",
                    "job_id": frame["job_id"],
                    "event": {"type": "run.completed", "run_id": "run-A", "data": {}},
                }
            )
        )
        try:
            received = await asyncio.wait_for(asyncio.shield(task), 0.3)
        except TimeoutError:
            pass
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await stream.aclose()
        await a.close()
        await b.close()
        await hub.stop()
    assert received is None, "Hub accepted B's frame for A's job without sender ownership validation"


@pytest.mark.asyncio
@blocker
async def test_cancellation_requires_remote_stop_ack_before_forgetting_job():
    """A deliberately uncooperative loopback daemon never acknowledges cleanup."""
    hub = daemon.AgentRuntimeDaemonHub()
    await hub.start(host="127.0.0.1", port=0, token="fixture-A")
    ws = await connect(hub, "A")
    task = asyncio.create_task(collect(hub.run_job(daemon_id="A", payload={}, tools=None, timeout=3)))
    try:
        start = json.loads(await asyncio.wait_for(ws.recv(), 2))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        cleanup = json.loads(await asyncio.wait_for(ws.recv(), 2))
        assert cleanup == {"type": "run.cleanup", "job_id": start["job_id"]}
        retained = start["job_id"] in hub._jobs
    finally:
        await ws.close()
        await hub.stop()
    assert retained, "Cancellation forgot the job before remote stop acknowledgement or durable fencing"


@blocker
def test_codex_run_homes_do_not_share_credentials_or_session_files(tmp_path, monkeypatch):
    module, _ = load_plugin("codex-agent")
    shared = tmp_path / "host-home"
    shared.mkdir()
    (shared / "auth.json").write_text('{"fixture":"not-a-real-credential"}')
    (shared / "sessions").mkdir()
    (shared / "sessions" / "A.jsonl").write_text("only-A-session")
    monkeypatch.setenv("CODEX_HOME", str(shared))
    a, _ = module._prepare_local_codex_home(str(tmp_path / "A"), "same-session", {}, "")
    b, _ = module._prepare_local_codex_home(str(tmp_path / "B"), "same-session", {}, "")
    ah, bh = Path(a["CODEX_HOME"]), Path(b["CODEX_HOME"])
    assert ah != bh
    assert not (bh / "auth.json").exists() and not (bh / "sessions" / "A.jsonl").exists(), (
        "Random run-home names still expose host auth and shared persisted sessions"
    )


@pytest.mark.asyncio
@blocker
async def test_acp_process_cannot_inherit_worker_environment(tmp_path, monkeypatch):
    module, _ = load_plugin("acp-agent-runner")
    sentinel = "synthetic-other-installation-token"
    monkeypatch.setenv("CODING_FIXTURE_HOST_SECRET", sentinel)
    result = tmp_path / "child.json"
    script = (
        "import os,json,time,pathlib; "
        f"pathlib.Path({str(result)!r}).write_text(json.dumps({{'secret':os.getenv('CODING_FIXTURE_HOST_SECRET'),"
        "'cwd':os.getcwd()})); time.sleep(10)"
    )
    client = module.AcpStdioClient(command=sys.executable, args=["-c", script], cwd=str(tmp_path), env={})
    async with client:
        async with asyncio.timeout(3):
            while not result.exists():
                await asyncio.sleep(0.01)
        child = json.loads(result.read_text())
    assert child["cwd"] == str(tmp_path)
    assert child["secret"] is None, "Unbound subprocess inherited the worker's synthetic secret"


def test_real_b5_proxy_has_box_binding_but_no_duplex_process_or_daemon_authority():
    assert importlib.metadata.version("langbot-plugin") == "0.6.0b5"
    runner = Runner()
    runner.bind_runtime(plugin_runtime_handler=NoHostCalls())
    api = runner.get_run_api(context("scope-probe"))
    assert api.run_id == "scope-probe"
    assert callable(api.acquire_box) and callable(api.bind_box) and callable(api.call_tool)
    public = {name for name in dir(api) if not name.startswith("_")}
    assert not any("daemon" in name or "process" in name or "stdin" in name for name in public)


@pytest.mark.asyncio
@pytest.mark.parametrize("folder,name,version,key", PLUGINS)
@admission_blocker
async def test_exact_previous_archive_is_admitted_by_b5(folder, name, version, key, tmp_path):
    directory = os.environ.get("CODING_RUNNER_RELEASE_DIR")
    if not directory:
        pytest.skip("set CODING_RUNNER_RELEASE_DIR to independently retained release archives")
    archive = Path(directory) / f"langbot-team-{name}-{version}.lbpkg"
    data = archive.read_bytes()
    # Confirm previous archive's executable/dependency bytes match current source.
    with zipfile.ZipFile(archive) as package:
        for member in package.namelist():
            if member.endswith(".py") or member == "requirements.txt":
                assert package.read(member) == (ROOT / folder / member).read_bytes()
    store = PluginArtifactStore(tmp_path / "runtime")
    artifact = store.install_package(data, hashlib.sha256(data).hexdigest())
    assert artifact.plugin_name == name
    dependency_store = PluginDependencyEnvironmentStore(tmp_path / "runtime")

    async def forbidden_installer(*args):
        pytest.fail("An incompatible SDK requirement must fail before dependency installation")

    try:
        await dependency_store.prepare(artifact, runtime_fingerprint="coding-blocker-b5", installer=forbidden_installer)
    finally:
        # Only the fixture's immutable trees need writable directories for teardown.
        for parent, _dirs, _files in os.walk(tmp_path):
            os.chmod(parent, 0o700)
