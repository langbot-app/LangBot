from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources, ModelResource, ToolResource

from pkg.agent_core import LangBotContextHooks, LangBotToolExecutor
from pkg.messages import build_platform_tools_system_message
from pkg.run_assembly import AgentRunAssembler, NoAuthorizedModelError
from tests.test_runner import FakeRunnerAPIProxy, make_context


@pytest.mark.asyncio
async def test_assembler_builds_authorized_loop_inputs() -> None:
    api = FakeRunnerAPIProxy(
        models=[ModelResource(model_id="model-primary"), ModelResource(model_id="model-fallback")],
        tools=[ToolResource(tool_name="qa_plugin_echo")],
    )
    ctx = make_context(
        config={
            "model": {"primary": "model-primary", "fallbacks": ["model-missing", "model-fallback"]},
            "prompt": [{"role": "system", "content": "Static prompt"}],
            "remove-think": True,
            "max-tool-iterations": 7,
            "max-tool-result-chars": 32,
            "tool-execution-mode": "serial",
        },
        resources=AgentResources(
            models=[ModelResource(model_id="model-primary"), ModelResource(model_id="model-fallback")],
            tools=[ToolResource(tool_name="qa_plugin_echo")],
        ),
        input_text="hello",
        runtime_metadata={"streaming_supported": False},
    )

    assembly = await AgentRunAssembler(api, ctx).assemble()

    assert assembly.model_ids == ["model-primary", "model-fallback"]
    assert [tool.name for tool in assembly.tools] == ["qa_plugin_echo"]
    assert isinstance(assembly.tool_executor, LangBotToolExecutor)
    assert assembly.tool_executor.allowed_tools == {"qa_plugin_echo"}
    assert assembly.tool_executor.max_result_chars == 32
    assert isinstance(assembly.hooks, LangBotContextHooks)
    assert assembly.streaming is False
    assert assembly.max_tool_iterations == 7
    assert assembly.tool_execution_mode == "serial"
    assert assembly.remove_think is True
    assert [message.role for message in assembly.messages] == ["system", "user"]
    assert assembly.messages[-1].content == "hello"
    api.get_tool_detail.assert_awaited_once_with("qa_plugin_echo")


@pytest.mark.asyncio
async def test_assembler_disables_streaming_when_delivery_does_not_support_it() -> None:
    api = FakeRunnerAPIProxy(
        models=[ModelResource(model_id="model-primary")],
    )
    ctx = make_context(
        config={"model": {"primary": "model-primary", "fallbacks": []}},
        resources=AgentResources(models=[ModelResource(model_id="model-primary")]),
        runtime_metadata={"streaming_supported": True},
        delivery_supports_streaming=False,
    )

    assembly = await AgentRunAssembler(api, ctx).assemble()

    assert assembly.streaming is False


@pytest.mark.asyncio
async def test_assembler_raises_when_configured_models_are_not_authorized() -> None:
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="authorized-model")])
    api.get_tool_detail = AsyncMock()
    ctx = make_context(
        config={"model": {"primary": "unauthorized-model", "fallbacks": []}},
        resources=AgentResources(models=[ModelResource(model_id="authorized-model")]),
    )

    with pytest.raises(NoAuthorizedModelError):
        await AgentRunAssembler(api, ctx).assemble()

    api.get_tool_detail.assert_not_awaited()


def test_platform_action_tools_add_run_scoped_safety_guidance() -> None:
    ctx = make_context(
        resources=AgentResources(
            tools=[
                ToolResource(
                    tool_name="event_reply",
                    tool_type="platform",
                    description="Reply to the current event",
                )
            ]
        )
    )

    message = build_platform_tools_system_message(ctx)

    assert message is not None
    assert "event_reply" in message.content
    assert "targets frozen by LangBot" in message.content
    assert "never claim an action succeeded" in message.content


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled, entitled", [(False, True), (True, False), (False, False)])
async def test_sandbox_tools_require_both_config_and_box_capability(enabled, entitled):
    tools = [ToolResource(tool_name=name) for name in ["exec", "read", "write", "edit", "glob", "grep", "echo"]]
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")], tools=tools)
    ctx = make_context(
        config={"model": {"primary": "primary"}, "box-enabled": enabled},
        resources=AgentResources(models=api.get_allowed_models(), tools=tools),
    )
    ctx.context.available_apis.box = entitled

    assembly = await AgentRunAssembler(api, ctx).assemble()

    assert [tool.name for tool in assembly.tools] == ["echo"]
    assert assembly.tool_executor.allowed_tools == {"echo"}
    api.get_tool_detail.assert_awaited_once_with("echo")


@pytest.mark.asyncio
async def test_build_llm_tools_uses_prefilled_schema_without_fetch() -> None:
    """Host-prefilled ToolResource.parameters avoid a get_tool_detail round-trip."""
    from unittest.mock import Mock

    from pkg.model_calling import build_llm_tools

    api = Mock()
    api.get_tool_detail = AsyncMock(side_effect=AssertionError("must not fetch when prefilled"))
    tool_resources = [
        ToolResource(
            tool_name="echo",
            description="Echo tool",
            parameters={"type": "object", "properties": {}},
        ),
    ]

    tools = await build_llm_tools(api, {"echo"}, tool_resources)

    assert [t.name for t in tools] == ["echo"]
    assert tools[0].parameters == {"type": "object", "properties": {}}
    api.get_tool_detail.assert_not_awaited()


@pytest.mark.parametrize("mock", [True, False])
def test_platform_mock_guidance_is_scoped_to_debug_runs(mock):
    ctx = make_context(resources=AgentResources(tools=[ToolResource(tool_name="event_reply", tool_type="platform")]))
    ctx.delivery.platform_capabilities = {"debug_mock": mock}
    message = build_platform_tools_system_message(ctx)
    assert message is not None
    assert ("A successful mock result fully satisfies" in message.content) is mock
    assert "empty object schema" in message.content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type",
    [
        "group.member_joined",
        "group.member_left",
        "friend.request_received",
        "feedback.received",
        "message.edited",
        "message.deleted",
        "message.reaction",
        "custom.probe",
    ],
)
async def test_event_data_reaches_model_context(event_type):
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="model-primary")])
    ctx = make_context(
        config={"model": {"primary": "model-primary"}},
        resources=AgentResources(models=[ModelResource(model_id="model-primary")]),
        input_text="Read probe",
    )
    ctx.event.event_type = event_type
    ctx.event.data = {"probe": "E2E-42", "nested": {"member_id": "member-1"}}
    assembly = await AgentRunAssembler(api, ctx).assemble()
    facts = assembly.messages[-2]
    assert facts.role == "user"
    assert event_type in facts.content
    assert '"probe": "E2E-42"' in facts.content
    assert '"member_id": "member-1"' in facts.content
    assert assembly.messages[-1].content == "Read probe"
