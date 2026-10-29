"""Shared-placement properties for the DashScope runner on one component object.

The Runner component is a process-wide singleton under shared-runtime-v1, so two
installations drive the same object. These tests pin that each invocation reads
its own configuration/credentials, that nothing tenant-scoped survives on the
object or in module globals, that the runner derives no upstream identity, and
that the synchronous vendor SDK is isolated in a fresh private subprocess per
invocation.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

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
from langbot_plugin.api.entities.builtin.runner.result import RunnerResultType
from langbot_plugin.api.proxies.invocation import bind_invocation, current_binding, current_config
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import pkg.asset_gateway as asset_gateway  # noqa: E402
import pkg.vendor_process as vendor_process  # noqa: E402
from components.runner import default as runner_module  # noqa: E402

# One simulated vendor chunk; the worker frame wraps it as {"item": ...}.
CHUNK = {"status_code": 200, "output": {"text": "hello", "finish_reason": "stop", "session_id": ""}}
MINIMAL_ENV_KEYS = {"PATH", "TMPDIR", "HOME", "PYTHONIOENCODING", "PYTHONUNBUFFERED"}

TENANT_A = {"api_key": "dashscope-key-AAA", "app_id": "app-AAA"}
TENANT_B = {"api_key": "dashscope-key-BBB", "app_id": "app-BBB"}
SECRETS = (TENANT_A["api_key"], TENANT_B["api_key"])


def _binding(installation: str, *, workspace: str = "workspace-1") -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


def _config(tenant: dict[str, str]) -> dict[str, object]:
    return {
        "app-type": "agent",
        "api-key": tenant["api_key"],
        "app-id": tenant["app_id"],
        "remove-think": False,
        "timeout": 30,
        "streaming": False,
    }


def _ctx(config: dict[str, object], run_id: str) -> RunnerContext:
    return RunnerContext(
        run_id=run_id,
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id=f"evt-{run_id}",
            event_type="message.received",
            source="host_adapter",
        ),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="pipeline", supports_streaming=False),
        resources=AgentResources(),
        runtime=AgentRuntimeContext(),
        state=AgentRunState(),
        config=config,
    )


class _FakeStdin:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data) -> None:
        self.data += bytes(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


class _FakeStdout:
    def __init__(self, frames: list) -> None:
        self._frames = list(frames)

    async def readline(self) -> bytes:
        if self._frames:
            return json.dumps({"item": self._frames.pop(0)}).encode("utf-8") + b"\n"
        return b""

    async def read(self, size: int = -1) -> bytes:
        return b""


class _FakeProcess:
    def __init__(self, frames: list) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(frames)
        self.returncode = None

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def _runner_with_handler():
    runner = runner_module.DefaultRunner()
    handler = object()
    runner._plugin_runtime_handler = handler
    return runner, handler


def _install_fake_vendor(monkeypatch, spawns: list) -> None:
    """Record each vendor subprocess launch instead of spawning it."""

    async def fake_create_subprocess_exec(*args, **kwargs):
        process = _FakeProcess([CHUNK])
        spawns.append((args, kwargs, process))
        return process

    monkeypatch.setattr(vendor_process.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)


async def _drive(runner, handler, binding, config, run_id):
    with bind_invocation(handler, config=config, binding=binding):
        # The invocation binding is what get_plugin_config() resolves against.
        assert runner.get_plugin_config() == config
        return [result async for result in runner.run(_ctx(config, run_id))]


def _contains(value, needle: str, depth: int = 0) -> bool:
    if depth > 12:
        return False
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(
            _contains(key, needle, depth + 1) or _contains(item, needle, depth + 1) for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains(item, needle, depth + 1) for item in value)
    return False


def _payload(process: _FakeProcess) -> dict:
    return json.loads(process.stdin.data.decode("utf-8"))


def test_each_binding_gets_its_own_configuration_and_credentials(monkeypatch):
    runner, handler = _runner_with_handler()
    spawns = []
    _install_fake_vendor(monkeypatch, spawns)
    first_results = asyncio.run(_drive(runner, handler, _binding("a"), _config(TENANT_A), "run-a"))
    second_results = asyncio.run(_drive(runner, handler, _binding("b"), _config(TENANT_B), "run-b"))

    assert len(spawns) == 2
    first_payload, second_payload = _payload(spawns[0][2]), _payload(spawns[1][2])
    assert first_payload["kwargs"]["api_key"] == TENANT_A["api_key"]
    assert first_payload["kwargs"]["app_id"] == TENANT_A["app_id"]
    assert second_payload["kwargs"]["api_key"] == TENANT_B["api_key"]
    assert second_payload["kwargs"]["app_id"] == TENANT_B["app_id"]
    assert first_results[-1].type is RunnerResultType.RUN_COMPLETED
    assert second_results[-1].type is RunnerResultType.RUN_COMPLETED


def test_vendor_subprocess_is_per_invocation_with_private_environment(monkeypatch):
    runner, handler = _runner_with_handler()
    spawns = []
    _install_fake_vendor(monkeypatch, spawns)
    asyncio.run(_drive(runner, handler, _binding("a"), _config(TENANT_A), "run-a"))
    asyncio.run(_drive(runner, handler, _binding("b"), _config(TENANT_B), "run-b"))

    assert len(spawns) == 2
    first_cwd = spawns[0][1]["cwd"]
    second_cwd = spawns[1][1]["cwd"]
    assert spawns[0][2] is not spawns[1][2]
    # A fresh private directory per invocation, never the process working directory.
    assert first_cwd != second_cwd
    assert os.path.realpath(first_cwd) != os.path.realpath(os.getcwd())

    for _, kwargs, process in spawns:
        env = kwargs["env"]
        assert set(env) == MINIMAL_ENV_KEYS
        assert env["PATH"] == os.defpath
        assert env["HOME"] == kwargs["cwd"]
        assert env["TMPDIR"] == kwargs["cwd"]
        # No inherited provider secrets or import paths leak into the child.
        assert "PYTHONPATH" not in env
        # The child is reaped (killed) before the invocation returns.
        assert process.returncode is not None
        # The private directory is removed after reaping.
        assert not os.path.exists(kwargs["cwd"])


def test_shared_object_retains_no_tenant_state(monkeypatch):
    runner, handler = _runner_with_handler()
    spawns = []
    _install_fake_vendor(monkeypatch, spawns)
    asyncio.run(_drive(runner, handler, _binding("a"), _config(TENANT_A), "run-a"))
    asyncio.run(_drive(runner, handler, _binding("b"), _config(TENANT_B), "run-b"))

    for secret in SECRETS:
        assert not _contains(vars(runner), secret)
        for module_name, module in list(sys.modules.items()):
            tracked = module_name == "pkg" or module_name.startswith("pkg.") or module is runner_module
            if not tracked:
                continue
            for value in vars(module).values():
                if isinstance(value, (dict, list, set)):
                    assert not _contains(value, secret), f"{module_name} retains tenant state"


def test_runner_derives_no_upstream_identity():
    # Unlike coze/dify/n8n/tbox/weknora, DashScope sends no upstream user identity,
    # so it must not carry a per-run identity helper.
    assert not hasattr(runner_module.DefaultRunner, "_get_user_tag")
    assert not hasattr(runner_module.DefaultRunner, "_get_user_id")


GATEWAY_CONFIG = {
    "asset_gateway_host": "127.0.0.1",
    "asset_gateway_port": 0,
    "asset_gateway_request_timeout": 5.0,
    "asset_gateway_token_ttl": 60.0,
}


class _GatewayOwner:
    """Stand-in for the process-wide component object that owns the shared pool."""

    def __init__(self, handler):
        self._plugin_runtime_handler = handler


def _context_tenant_state(handler):
    """Invocation state visible from the current Context.

    An ended invocation object that is still referenced by a Context raises on
    lookup; that marker is exactly the residue this suite forbids.
    """
    try:
        return current_binding(handler), current_config(handler)
    except RuntimeError as exc:
        return f"ended-invocation-retained: {exc}", None


def test_gateway_listener_creation_runs_without_tenant_context(monkeypatch):
    handler = object()
    owner = _GatewayOwner(handler)
    observed: list[tuple] = []

    async def scenario():
        real_start_server = asyncio.start_server

        async def spy_start_server(*args, **kwargs):
            observed.append(_context_tenant_state(handler))
            return await real_start_server(*args, **kwargs)

        monkeypatch.setattr(asyncio, "start_server", spy_start_server)
        with bind_invocation(handler, config=_config(TENANT_A), binding=_binding("a")):
            registration = await asset_gateway.register_assets(
                owner, object(), _ctx(_config(TENANT_A), "run-a"), dict(GATEWAY_CONFIG)
            )
        await registration.stop()

    asyncio.run(scenario())

    assert observed, "the shared listener was never created"
    assert observed[0] == (None, None), "the listener was created inside the caller's tenant invocation context"


def test_shared_listener_retains_no_revoked_tenant_context(monkeypatch):
    handler = object()
    owner = _GatewayOwner(handler)
    accepted: list[tuple] = []

    async def scenario():
        real_connected = asset_gateway.Gateway.connected

        def probing_connected(self, reader, writer):
            # Runs in the Context that the listener's accept handle retained.
            accepted.append(_context_tenant_state(handler))
            return real_connected(self, reader, writer)

        monkeypatch.setattr(asset_gateway.Gateway, "connected", probing_connected)

        with bind_invocation(handler, config=_config(TENANT_A), binding=_binding("a")):
            registration_a = await asset_gateway.register_assets(
                owner, object(), _ctx(_config(TENANT_A), "run-a"), dict(GATEWAY_CONFIG)
            )
        with bind_invocation(handler, config=_config(TENANT_B), binding=_binding("b")):
            registration_b = await asset_gateway.register_assets(
                owner, object(), _ctx(_config(TENANT_B), "run-b"), dict(GATEWAY_CONFIG)
            )

        # A is revoked and gone; B keeps the same shared listener alive.
        await registration_a.stop()
        assert owner._asset_gateway_pool, "listener must survive while B is still registered"

        port = int(registration_b.endpoint.rsplit(":", 1)[1])
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        for _ in range(200):
            if accepted:
                break
            await asyncio.sleep(0.01)
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        await registration_b.stop()

    asyncio.run(scenario())

    assert accepted, "the shared listener never accepted the probe connection"
    for binding, config in accepted:
        assert binding is None, f"listener retained a tenant binding after revocation: {binding!r}"
        assert config is None, f"listener retained tenant configuration after revocation: {config!r}"


async def _post_mcp(port: int, payload: dict, token: str = "") -> tuple[str, dict]:
    """Send one JSON-RPC request to the listener; return (status line, body)."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    body = json.dumps(payload).encode()
    head = f"POST /mcp HTTP/1.1\r\nHost: listener\r\nContent-Length: {len(body)}\r\n".encode()
    if token:
        head += f"Authorization: Bearer {token}\r\n".encode()
    writer.write(head + b"\r\n" + body)
    await writer.drain()
    raw = (await reader.read()).decode("latin1")
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    status, _, rest = raw.partition("\r\n")
    return status, json.loads(rest.split("\r\n\r\n", 1)[1])


def _call_payload(token: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "demo_tool", "arguments": {"run_token": token}},
    }


def test_only_a_valid_run_token_enters_the_registration_invocation_context(monkeypatch):
    handler = object()
    owner = _GatewayOwner(handler)
    seen: list[tuple] = []

    async def scenario():
        with bind_invocation(handler, config=_config(TENANT_A), binding=_binding("a")):
            registration = await asset_gateway.register_assets(
                owner, object(), _ctx(_config(TENANT_A), "run-a"), dict(GATEWAY_CONFIG)
            )

            async def fake_call_mcp_tool(name, arguments):
                seen.append(_context_tenant_state(handler))
                return {"content": [{"type": "text", "text": "ok"}]}

            monkeypatch.setattr(registration.tools, "call_mcp_tool", fake_call_mcp_tool)
            port = int(registration.endpoint.rsplit(":", 1)[1])

            # A wrong token is rejected in the tenant-free listener context.
            _, body = await _post_mcp(port, _call_payload("wrong-token"))
            assert body["result"]["isError"] is True
            assert not seen

            # A valid token enters the registration's own invocation context.
            _, body = await _post_mcp(port, _call_payload(registration.token), token=registration.token)
            assert body["result"]["content"][0]["text"] == "ok"
            await registration.stop()

    asyncio.run(scenario())

    assert len(seen) == 1
    binding, config = seen[0]
    assert binding == _binding("a")
    assert config is not None and dict(config) == _config(TENANT_A)
