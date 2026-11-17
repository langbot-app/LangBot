from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.runner.input import InputAttachment, InputAttachmentData
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources, ModelResource, ToolResource
from langbot_plugin.api.proxies.runner import RunnerAPIProxy

from pkg.agent_core import LangBotContextHooks, LangBotToolExecutor, ToolCallRequest
from pkg.messages import build_platform_tools_system_message
from pkg.run_assembly import AgentRunAssembler, NoAuthorizedModelError
from tests.test_runner import FakeRunnerAPIProxy, make_context


@pytest.mark.asyncio
@pytest.mark.parametrize("granted,has_attachment", [(False, True), (True, False), (True, True)])
async def test_input_reader_is_discovered_from_the_run_grant_and_uses_installed_sdk_contract(granted, has_attachment):
    """Released SDKs exercise their raw API; the coordinated SDK must preserve structured media."""
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="model-primary")])
    ctx = make_context(
        config={"model": {"primary": "model-primary"}, "box-enabled": False},
        resources=AgentResources(models=[ModelResource(model_id="model-primary")]),
    )
    ctx.context.available_apis.input_attachments = granted
    ctx.input.attachments = [InputAttachment(ref="att-1", type="image")] if has_attachment else []
    payload = "data:image/png;base64,cHJpdmF0ZQ=="
    api.read_input_attachment_content = AsyncMock(
        return_value=[
            {"type": "text", "text": '{"ref":"att-1"}'},
            {"type": "image_base64", "image_base64": payload},
        ]
    )
    api.read_input_attachment = AsyncMock(
        return_value=InputAttachmentData(
            ref="att-1",
            name="legacy.txt",
            mime_type="text/plain",
            data=b"legacy-input",
        )
    )
    api._results = asyncio.Queue()
    api._run_id = "input-run"
    assembly = await AgentRunAssembler(api, ctx).assemble()
    names = {tool.name for tool in assembly.tools}
    assert ("langbot_read_input_attachment" in names) is (granted and has_attachment)
    if not (granted and has_attachment):
        api.read_input_attachment.assert_not_awaited()
        api.read_input_attachment_content.assert_not_awaited()
        return
    prepared = assembly.tool_executor.prepare(
        ToolCallRequest.from_raw(
            {
                "id": "call-read",
                "function": {"name": "langbot_read_input_attachment", "arguments": '{"ref":"att-1"}'},
            }
        )
    )
    outcome = await assembly.tool_executor.execute(prepared)
    if not hasattr(RunnerAPIProxy, "read_input_attachment_content"):
        assert outcome.error is None and outcome.model_only_messages == []
        assert outcome.result == {
            "ref": "att-1",
            "name": "legacy.txt",
            "mime_type": "text/plain",
            "size": len(b"legacy-input"),
            "content_base64": base64.b64encode(b"legacy-input").decode(),
        }
        api.read_input_attachment.assert_awaited_once_with("att-1")
        api.read_input_attachment_content.assert_not_awaited()
        return
    assert outcome.error is None and outcome.model_only_messages[0].content[0].image_base64 == payload
    api.read_input_attachment_content.assert_awaited_once_with(
        ref="att-1",
        mode="auto",
        offset=0,
        max_chars=8192,
        page_start=1,
        page_end=None,
    )
    assert payload not in outcome.message.content
    started, completed = api._results.get_nowait(), api._results.get_nowait()
    assert started.type.value == "tool.call.started" and completed.type.value == "tool.call.completed"
    assert payload not in json.dumps(completed.data)


@pytest.mark.asyncio
@pytest.mark.parametrize("granted,enabled", [(False, True), (True, False), (True, True)])
async def test_run_file_reader_uses_structured_media_only_with_box_grant(granted, enabled):
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="model-primary")])
    ctx = make_context(
        config={"model": {"primary": "model-primary"}, "box-enabled": enabled},
        resources=AgentResources(models=[ModelResource(model_id="model-primary")]),
    )
    ctx.context.available_apis.box = granted
    payload = "data:image/png;base64,cHJpdmF0ZQ=="
    api.read_run_file = AsyncMock(
        return_value=[{"type": "text", "text": "output"}, {"type": "image_base64", "image_base64": payload}]
    )
    api._results = asyncio.Queue()
    api._run_id = ctx.run_id
    assembly = await AgentRunAssembler(api, ctx).assemble()
    available = granted and enabled and hasattr(RunnerAPIProxy, "read_run_file")
    assert ("langbot_read_run_file" in {tool.name for tool in assembly.tools}) is available
    if not available:
        api.read_run_file.assert_not_awaited()
        return
    prepared = assembly.tool_executor.prepare(
        ToolCallRequest.from_raw(
            {"id": "read-output", "function": {"name": "langbot_read_run_file", "arguments": '{"file_id":"file-1"}'}}
        )
    )
    outcome = await assembly.tool_executor.execute(prepared)
    assert outcome.error is None and outcome.model_only_messages[0].content[0].image_base64 == payload
    assert api.read_run_file.await_args.kwargs["file_id"] == "file-1"
    assert payload not in outcome.message.content
    started, completed = api._results.get_nowait(), api._results.get_nowait()
    assert started.type.value == "tool.call.started" and completed.type.value == "tool.call.completed"
    assert payload not in json.dumps(completed.data)


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


@pytest.mark.parametrize("automatic_reply", [False, True])
@pytest.mark.parametrize(
    "tool_name, tool_type",
    [("event_reply", "platform"), ("event_get_actor", "platform"), ("event_reply", "plugin"), (None, None)],
)
def test_explicit_reply_guidance_requires_manual_delivery_and_authorized_platform_tool(
    automatic_reply, tool_name, tool_type
):
    tools = [ToolResource(tool_name=tool_name, tool_type=tool_type)] if tool_name else []
    ctx = make_context(resources=AgentResources(tools=tools))
    ctx.delivery.automatic_reply = automatic_reply

    message = build_platform_tools_system_message(ctx)

    content = message.content if message else ""
    expected = not automatic_reply and tool_name == "event_reply" and tool_type == "platform"
    assert ("Your final output text will not be sent to the user in this run." in content) is expected
    assert ("To reply to the user, you must call `event_reply` with the reply text." in content) is expected
    assert ("You may omit `event_reply` only when no reply is needed" in content) is expected
    assert ("the event requires no response" in content) is expected
    assert ("replying is outside this processor's responsibilities" in content) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("automatic_reply", [False, True])
@pytest.mark.parametrize("workspace_mode", [None, "direct", "progressive"])
async def test_assembler_includes_delivery_guidance_in_model_system_prompt(automatic_reply, workspace_mode):
    tools = [ToolResource(tool_name="event_reply", tool_type="platform")]
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")], tools=tools)
    ctx = make_context(
        config={
            "model": {"primary": "primary"},
            "prompt": [{"role": "system", "content": "Be helpful."}],
            "workspace-direct-threshold": 0 if workspace_mode == "progressive" else 10,
        },
        resources=AgentResources(models=api.get_allowed_models(), tools=tools),
        input_text="hello",
    )
    # Workspace tools come from the operations LangBot selected for this run.
    ctx.resources = SimpleNamespace(
        **{name: getattr(ctx.resources, name) for name in ("models", "tools", "knowledge_bases", "skills")},
        workspace_operations=[{"id": "bot.list"}] if workspace_mode else [],
    )
    ctx.delivery.automatic_reply = automatic_reply

    assembly = await AgentRunAssembler(api, ctx).assemble()

    assert assembly.messages[0].role == "system"
    assert "Be helpful." in assembly.messages[0].content
    assert ("you must call `event_reply`" in assembly.messages[0].content) is not automatic_reply
    assert assembly.messages[-1].content == "hello"
    tool_names = {tool.name for tool in assembly.tools}
    assert "event_reply" in tool_names
    assert ("ws_bot__list" in tool_names) is (workspace_mode == "direct")
    assert ("workspace_call" in tool_names) is (workspace_mode == "progressive")
    assert ("follow progressive disclosure" in assembly.messages[0].content) is (workspace_mode == "progressive")


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
