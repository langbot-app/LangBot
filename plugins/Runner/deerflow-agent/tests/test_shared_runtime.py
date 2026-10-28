"""Shared-placement properties for the DeerFlow runner on one component object.

The Runner component is a process-wide singleton under shared-runtime-v1, so two
installations drive the same object. These tests pin that each invocation reads
its own configuration/credentials, that nothing tenant-scoped survives on the
object or in module globals, and that the runner derives no upstream identity.
"""

from __future__ import annotations

import asyncio
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
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.runner import default as runner_module  # noqa: E402

TENANT_A = {"api_base": "https://deerflow-a.example.com", "api_key": "deerflow-key-AAA"}
TENANT_B = {"api_base": "https://deerflow-b.example.com", "api_key": "deerflow-key-BBB"}
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
        "api-base": tenant["api_base"],
        "api-key": tenant["api_key"],
        "auth-header": "",
        "assistant-id": "lead_agent",
        "model-name": "",
        "thinking-enabled": False,
        "plan-mode": False,
        "subagent-enabled": False,
        "max-concurrent-subagents": 3,
        "timeout": 30,
        "recursion-limit": 1000,
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
        state=AgentRunState(conversation={"external.thread_id": "thread-1"}),
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
    real_client = runner_module.AsyncDeerFlowClient

    def factory(**kwargs):
        client = real_client(**kwargs)
        created.append(client)

        async def create_thread(timeout=20):
            return {"thread_id": "thread-1"}

        async def stream_run(thread_id, payload, timeout):
            if False:  # pragma: no cover - an empty async generator
                yield {}

        client.create_thread = create_thread
        client.stream_run = stream_run
        return client

    runner_module.AsyncDeerFlowClient = factory
    try:
        with bind_invocation(handler, config=config, binding=binding):
            # The invocation binding is what get_plugin_config() resolves against.
            assert runner.get_plugin_config() == config
            results = [result async for result in runner.run(_ctx(config, run_id))]
    finally:
        runner_module.AsyncDeerFlowClient = real_client
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
    # The real client derives its Authorization header from the invocation config.
    assert first_created[0].headers == {"Authorization": f"Bearer {TENANT_A['api_key']}"}
    assert second_created[0].headers == {"Authorization": f"Bearer {TENANT_B['api_key']}"}
    assert first_created[0].api_base == TENANT_A["api_base"]
    assert second_created[0].api_base == TENANT_B["api_base"]
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
    # Unlike coze/dify/n8n/tbox/weknora, DeerFlow sends no upstream user identity,
    # so it must not carry a per-run identity helper.
    assert not hasattr(runner_module.DefaultRunner, "_get_user_tag")
    assert not hasattr(runner_module.DefaultRunner, "_get_user_id")
