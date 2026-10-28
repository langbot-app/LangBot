"""Real SDK b5, local fixtures only; no vendor accounts or live claims."""

import asyncio
import importlib.util
import inspect
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from langbot_plugin.api.entities.builtin.runner import (
    ActorContext,
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRuntimeContext,
    AgentTrigger,
    ConversationContext,
    DeliveryContext,
    RunnerContext,
)
from langbot_plugin.api.proxies.invocation import bind_invocation

ROOT = Path(os.environ.get("HTTP_RUNNER_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
GATEWAYS = ["coze", "dashscope", "dify", "langflow", "n8n"]
IDENTITIES = ["coze", "dify", "n8n", "tbox", "weknora"]
IDENTITY_ERRORS = {
    "coze": ("CozeConfigError", "AsyncCozeClient"),
    "dify": ("DifyConfigError", "AsyncDifyClient"),
    "n8n": ("N8nConfigError", "AsyncN8nClient"),
    "tbox": ("TboxConfigError", "AsyncTboxClient"),
    "weknora": ("WeKnoraConfigError", "AsyncWeKnoraClient"),
}


@contextmanager
def load(name):
    saved = {k: v for k, v in sys.modules.items() if k == "pkg" or k.startswith("pkg.")}
    for k in saved:
        del sys.modules[k]
    path = ROOT / (name + "-agent")
    sys.path.insert(0, str(path))
    key = "cert_" + name
    try:
        spec = importlib.util.spec_from_file_location(key, path / "components/runner/default.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        yield module, module.DefaultRunner()
    finally:
        sys.path.remove(str(path))
        sys.modules.pop(key, None)
        for k in list(sys.modules):
            if k == "pkg" or k.startswith("pkg."):
                del sys.modules[k]
        sys.modules.update(saved)


def context(workspace="A", *, actor=True):
    return RunnerContext(
        run_id="fixture",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="event", event_type="message.received", source="fixture"),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="fixture"),
        resources=AgentResources(),
        runtime=AgentRuntimeContext(),
        actor=ActorContext(actor_type="user", actor_id="same-actor") if actor else None,
        conversation=ConversationContext(conversation_id="same-conversation", workspace_id=workspace),
    )


def identity(runner, ctx):
    return (getattr(runner, "_get_user_tag", None) or runner._get_user_id)(ctx)


async def collect(generator):
    return [result async for result in generator]


@contextmanager
def gateway_invocation(runner):
    # Registration must be owned by the same revocable authority as a real run.
    with bind_invocation(runner._plugin_runtime_handler):
        yield


@pytest.mark.parametrize("name", IDENTITIES)
def test_workspace_identity_collision(name):
    with load(name) as (_, runner):
        a, b = context("A"), context("B")
        a.config["workspace_id"] = b.config["workspace_id"] = "forged"
        assert identity(runner, a) != identity(runner, b)
        assert identity(runner, a) == identity(runner, context("A"))


@pytest.mark.parametrize("name", IDENTITIES)
def test_connection_binding_overrides_claimed_workspace(name):
    with load(name) as (_, a), load(name) as (_, b):
        a._plugin_runtime_handler = SimpleNamespace(
            bound_action_context=SimpleNamespace(instance_uuid="i", workspace_uuid="A", installation_uuid="install-a")
        )
        b._plugin_runtime_handler = SimpleNamespace(
            bound_action_context=SimpleNamespace(instance_uuid="i", workspace_uuid="B", installation_uuid="install-b")
        )
        assert identity(a, context(None)) != identity(b, context(None))


@pytest.mark.parametrize("name", IDENTITIES)
def test_sender_without_host_actor_is_refused_before_any_upstream_call(name, monkeypatch):
    error_name, client_name = IDENTITY_ERRORS[name]
    with load(name) as (module, runner):
        error_cls = getattr(module, error_name)

        with pytest.raises(error_cls) as refused:
            identity(runner, context(actor=False))
        assert refused.value.code == f"{name}.identity_unavailable"

        built = []

        class RecordingClient:
            def __init__(self, *args, **kwargs):
                built.append((args, kwargs))
                raise AssertionError("upstream client must not be built without a trusted Host actor")

        monkeypatch.setattr(module, client_name, RecordingClient)
        results = asyncio.run(collect(runner.run(context(actor=False))))
        assert [getattr(result.type, "value", str(result.type)) for result in results] == ["run.failed"]
        assert results[0].data["code"] == f"{name}.identity_unavailable"
        assert built == []


@pytest.mark.parametrize("name", GATEWAYS)
def test_gateway_overlap_has_independent_timeout_and_tokens(name):
    async def run(runner):
        runner.get_run_api = lambda ctx: SimpleNamespace()

        async def create(timeout):
            value = runner._create_asset_gateway_registration(
                context(),
                {
                    "asset_gateway_host": "127.0.0.1",
                    "asset_gateway_port": 0,
                    "asset_gateway_request_timeout": timeout,
                    "asset_gateway_token_ttl": 60,
                },
            )
            return await value if inspect.isawaitable(value) else value

        a = await create(0.5)
        b = None
        try:
            b = await create(1.5)
            assert a.gateway is not b.gateway
            assert a.gateway.request_timeout == 0.5
            assert b.gateway.request_timeout == 1.5
            assert a.token != b.token
            assert a.gateway._registration_for_token(b.token) is None
        finally:
            for registration in [a, b]:
                if registration:
                    value = registration.stop()
                    if inspect.isawaitable(value):
                        await value
                    # Historical SDK singleton needs explicit cleanup in RED.
                    if registration.gateway.__class__.__module__.startswith("langbot_plugin"):
                        registration.gateway.stop()

    with load(name) as (_, runner):
        with gateway_invocation(runner):
            asyncio.run(run(runner))


def test_dify_storage_transport_failure_not_misreported_absent():
    async def run(module, runner):
        async def broken(key):
            raise PermissionError("fixture denial")

        runner.get_run_api = lambda ctx: SimpleNamespace(get_plugin_storage=broken)
        with pytest.raises(PermissionError):
            await runner._load_interaction_continuation(context(), "id")

    with load("dify") as (m, runner):
        asyncio.run(run(m, runner))
