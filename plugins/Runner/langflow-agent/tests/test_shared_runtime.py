"""Shared-placement properties for the Langflow runner on one component object.

The Runner component is a process-wide singleton under shared-runtime-v1, so two
installations drive the same object. These tests pin that each invocation reads
its own configuration/credentials, that nothing tenant-scoped survives on the
object or in module globals, and that the runner derives no upstream identity.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from langbot_plugin.api.entities.builtin.runner import (
    ActorContext,
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
from components.runner import default as runner_module  # noqa: E402

TENANT_A = {"base_url": "https://langflow-a.example.com", "api_key": "langflow-key-AAA"}
TENANT_B = {"base_url": "https://langflow-b.example.com", "api_key": "langflow-key-BBB"}
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
        "base-url": tenant["base_url"],
        "api-key": tenant["api_key"],
        "flow-id": "flow-1",
        "input-type": "chat",
        "output-type": "chat",
        "tweaks": "{}",
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
        actor=ActorContext(actor_type="user", actor_id="user_1"),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="pipeline", supports_streaming=False),
        resources=AgentResources(),
        runtime=AgentRuntimeContext(),
        state=AgentRunState(conversation={"external.session_id": "session-1"}),
        config=config,
    )


def _runner_with_handler():
    runner = runner_module.DefaultRunner()
    handler = object()
    runner._plugin_runtime_handler = handler
    return runner, handler


async def _drive(runner, handler, binding, config, run_id):
    """Run one invocation through the shared object and return created clients/results."""
    created = []
    real_client = runner_module.AsyncLangflowClient

    def factory(**kwargs):
        client = real_client(**kwargs)
        created.append(client)

        async def run_flow(
            flow_id, input_value, input_type="chat", output_type="chat", tweaks=None, session_id=None, stream=True
        ):
            yield {"outputs": []}

        client.run_flow = run_flow
        return client

    runner_module.AsyncLangflowClient = factory
    try:
        with bind_invocation(handler, config=config, binding=binding):
            # The invocation binding is what get_plugin_config() resolves against.
            assert runner.get_plugin_config() == config
            results = [result async for result in runner.run(_ctx(config, run_id))]
    finally:
        runner_module.AsyncLangflowClient = real_client
    return created, results


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


def test_each_binding_gets_its_own_configuration_and_credentials():
    runner, handler = _runner_with_handler()
    first_created, first_results = asyncio.run(_drive(runner, handler, _binding("a"), _config(TENANT_A), "run-a"))
    second_created, second_results = asyncio.run(_drive(runner, handler, _binding("b"), _config(TENANT_B), "run-b"))

    assert len(first_created) == len(second_created) == 1
    assert first_created[0] is not second_created[0]
    # The real client derives its x-api-key header from the invocation config.
    assert first_created[0]._get_headers()["x-api-key"] == TENANT_A["api_key"]
    assert second_created[0]._get_headers()["x-api-key"] == TENANT_B["api_key"]
    assert first_created[0].base_url == TENANT_A["base_url"]
    assert second_created[0].base_url == TENANT_B["base_url"]
    assert first_results[-1].type is RunnerResultType.RUN_COMPLETED
    assert second_results[-1].type is RunnerResultType.RUN_COMPLETED


def test_shared_object_retains_no_tenant_state():
    runner, handler = _runner_with_handler()
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
    # Unlike coze/dify/n8n/tbox/weknora, Langflow sends no upstream user identity,
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
