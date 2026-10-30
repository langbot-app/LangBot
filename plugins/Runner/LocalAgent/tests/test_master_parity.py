"""Master behavior regressions using real SDK entities, no provider calls."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources, ModelResource

from components.runner.default import DefaultRunner
from tests.test_runner import FakeRunnerAPIProxy, make_context


@pytest.mark.asyncio
@pytest.mark.parametrize("host_prompt", [False, True])
async def test_date_grounding_reaches_real_runner_model_call(host_prompt):
    prompt = [{"role": "system", "content": "Keep this custom prompt."}]
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")])
    api.invoke_llm.return_value = Message(role="assistant", content="Grounded answer")
    api.get_prompt.return_value = prompt if host_prompt else []
    ctx = make_context(
        config={"model": {"primary": "primary"}, "prompt": prompt},
        resources=AgentResources(models=[ModelResource(model_id="primary")]),
        prompt_get=host_prompt,
        delivery_supports_streaming=False,
    )
    ctx.config.pop("date-grounding", None)  # Exercise production default, not deterministic test opt-out.
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    results = [result async for result in runner.run(ctx)]
    assert results[-1].type.value == "run.completed"
    content = api.invoke_llm.call_args.kwargs["messages"][0].content
    assert "Current date:" in content
    assert datetime.now(timezone.utc).strftime("%Y-%m-%d") in content
    assert "UTC" in content
    assert "verify with a search tool if one is available" in content
    assert "Keep this custom prompt." in content
    assert prompt == [{"role": "system", "content": "Keep this custom prompt."}]


@pytest.mark.asyncio
async def test_date_grounding_can_be_disabled():
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")])
    api.invoke_llm.return_value = Message(role="assistant", content="Answer")
    ctx = make_context(
        config={"model": {"primary": "primary"}, "date-grounding": False}, delivery_supports_streaming=False
    )
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    assert [result async for result in runner.run(ctx)][-1].type.value == "run.completed"
    assert all("Current date:" not in str(m.content) for m in api.invoke_llm.call_args.kwargs["messages"])


@pytest.mark.asyncio
async def test_date_grounding_creates_system_prompt_when_no_prompt_configured():
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")])
    api.invoke_llm.return_value = Message(role="assistant", content="Answer")
    ctx = make_context(config={"model": {"primary": "primary"}}, delivery_supports_streaming=False)
    ctx.config.pop("date-grounding", None)
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    assert [result async for result in runner.run(ctx)][-1].type.value == "run.completed"
    messages = api.invoke_llm.call_args.kwargs["messages"]
    assert messages[0].role == "system"
    assert "Current date:" in messages[0].content
    # The loop appends its assistant reply to the list after invocation.
    assert messages[1].role == "user"


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_reasoning_config_preserved_through_fallback_and_committed_tool_round(streaming):
    from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, MessageChunk, ToolCall
    from langbot_plugin.api.entities.builtin.runner.resources import ToolResource

    models = [ModelResource(model_id="primary"), ModelResource(model_id="fallback")]
    tools = [ToolResource(tool_name="echo")]
    api = FakeRunnerAPIProxy(models=models, tools=tools)
    config = {
        "model": {
            "primary": "primary",
            "fallbacks": ["unauthorized", "fallback"],
            "reasoning": {"primary": "high", "fallback": "low", "unauthorized": "max"},
        }
    }
    ctx = make_context(
        config=config, resources=AgentResources(models=models, tools=tools), delivery_supports_streaming=streaming
    )
    original = deepcopy(ctx.config)
    calls = []

    def reply(kwargs):
        calls.append(deepcopy(kwargs))
        if kwargs["llm_model_uuid"] == "primary":
            raise RuntimeError("primary offline")
        if not any(m.role == "tool" for m in kwargs["messages"]):
            return Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="echo-call", type="function", function=FunctionCall(name="echo", arguments="{}"))
                ],
            )
        return Message(role="assistant", content="done")

    async def invoke(**kwargs):
        return reply(kwargs)

    async def stream(**kwargs):
        response = reply(kwargs)
        yield MessageChunk(role="assistant", content=response.content, tool_calls=response.tool_calls, is_final=True)

    api.invoke_llm.side_effect = invoke
    api.invoke_llm_stream = stream
    api.call_tool.return_value = {"text": "tool result"}
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    results = [result async for result in runner.run(ctx)]
    assert results[-1].type.value == "run.completed"
    assert [call["llm_model_uuid"] for call in calls] == ["primary", "fallback", "fallback"]
    assert ctx.config == original
    assert [call["reasoning_level"] for call in calls] == ["high", "low", "low"]
    assert all(not call.get("extra_args") for call in calls)  # No vendor-specific arguments.
    assert calls[-1]["messages"][-1].role == "tool"
    api.call_tool.assert_awaited_once_with(tool_name="echo", parameters={})


@pytest.mark.asyncio
async def test_streaming_preserves_opaque_provider_fields_into_tool_followup():
    from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, MessageChunk, ToolCall
    from langbot_plugin.api.entities.builtin.runner.resources import ToolResource

    models = [ModelResource(model_id="primary")]
    tools = [ToolResource(tool_name="echo")]
    api = FakeRunnerAPIProxy(models=models, tools=tools)
    requests = []
    signature = {"opaque_signature": {"value": "signed-tool-state"}}

    async def stream(**kwargs):
        requests.append(deepcopy(kwargs))
        if len(requests) == 1:
            yield MessageChunk(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="signed-call",
                        type="function",
                        function=FunctionCall(name="echo", arguments="{"),
                        provider_specific_fields=signature,
                    )
                ],
                provider_specific_fields={"reasoning_content": "first ", "opaque_state": "message-state"},
            )
            yield MessageChunk(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="signed-call",
                        type="function",
                        function=FunctionCall(name="echo", arguments="}"),
                        provider_specific_fields={"other": "preserve"},
                    )
                ],
                provider_specific_fields={"reasoning_content": "second"},
                is_final=True,
            )
        else:
            yield MessageChunk(role="assistant", content="done", is_final=True)

    api.invoke_llm_stream = stream
    api.call_tool.return_value = {"ok": True}
    ctx = make_context(
        config={"model": {"primary": "primary"}},
        resources=AgentResources(models=models, tools=tools),
        delivery_supports_streaming=True,
    )
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    results = [result async for result in runner.run(ctx)]
    assert results[-1].type.value == "run.completed"
    assert len(requests) == 2
    assistant = next(m for m in requests[1]["messages"] if m.role == "assistant")
    assert assistant.provider_specific_fields == {"reasoning_content": "first second", "opaque_state": "message-state"}
    assert assistant.tool_calls[0].provider_specific_fields == {**signature, "other": "preserve"}
    assert assistant.tool_calls[0].function.arguments == "{}"


@pytest.mark.asyncio
async def test_streaming_retains_reasoning_only_prefix_without_leaking_failed_candidate():
    from langbot_plugin.api.entities.builtin.provider.message import MessageChunk

    from pkg.model_calling import StreamingModelCaller

    api = FakeRunnerAPIProxy()

    async def stream(**kwargs):
        if kwargs["llm_model_uuid"] == "primary":
            yield MessageChunk(role="assistant", content="", provider_specific_fields={"reasoning_content": "failed"})
            raise RuntimeError("before visible output")
        yield MessageChunk(role="assistant", content="", provider_specific_fields={"reasoning_content": "kept"})
        yield MessageChunk(role="assistant", content="answer", is_final=True)

    api.invoke_llm_stream = stream
    caller = StreamingModelCaller(api, ["primary", "fallback"], [Message(role="user", content="question")])
    chunks = [chunk async for chunk, _ in caller.stream()]
    assert caller.get_committed_model_id() == "fallback"
    assert caller.get_provider_specific_fields() == {"reasoning_content": "kept"}
    assert chunks[-1].provider_specific_fields == {"reasoning_content": "kept"}


@pytest.mark.asyncio
@pytest.mark.parametrize("host_prompt", [False, True])
async def test_structured_prompt_preserves_content_and_metadata_with_date(host_prompt):
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement

    prompt = [
        {"role": "system", "name": "policy", "content": [{"type": "text", "text": "保留规则"}]},
        {"role": "user", "content": "示例问题"},
        {"role": "assistant", "content": "示例答案"},
    ]
    original = deepcopy(prompt)
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")])
    api.invoke_llm.return_value = Message(role="assistant", content="Answer")
    api.get_prompt.return_value = prompt if host_prompt else []
    ctx = make_context(
        config={"model": {"primary": "primary"}, "prompt": prompt, "date-grounding": True},
        prompt_get=host_prompt,
        delivery_supports_streaming=False,
    )
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    results = [result async for result in runner.run(ctx)]
    assert results[-1].type.value == "run.completed"
    system = api.invoke_llm.call_args.kwargs["messages"][0]
    assert system.name == "policy"
    assert isinstance(system.content[0], ContentElement)
    assert "保留规则" in system.content[0].text
    assert "Current date:" in "".join(c.text or "" for c in system.content)
    assert prompt == original


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("date_grounding", [False, True])
@pytest.mark.parametrize(
    "prompt",
    [
        [],
        [{"role": "system", "content": "Keep this policy."}],
        [{"role": "system", "name": "policy", "content": [{"type": "text", "text": "Keep this policy."}]}],
        [
            {"role": "user", "content": "Example question"},
            {"role": "assistant", "content": "Example answer"},
        ],
    ],
    ids=["empty", "text", "structured", "few-shot"],
)
async def test_runner_guidance_accepts_strict_system_order_through_tool_loop(prompt, date_grounding, streaming):
    from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, MessageChunk, ToolCall
    from langbot_plugin.api.entities.builtin.runner.resources import SkillResource, ToolResource

    original = deepcopy(prompt)
    models = [ModelResource(model_id="primary")]
    tools = [ToolResource(tool_name="event_reply", tool_type="platform")]
    api = FakeRunnerAPIProxy(models=models, tools=tools)
    api.call_tool.return_value = "Tool finished"
    requests = []

    async def strict_model(**kwargs):
        messages = kwargs["messages"]
        if messages[0].role != "system" or any(m.role == "system" for m in messages[1:]):
            raise ValueError("System message must be at the beginning")
        requests.append([m.model_copy(deep=True) for m in messages])
        if len(requests) == 1:
            return Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call-1", type="function", function=FunctionCall(name="event_reply", arguments="{}"))
                ],
            )
        return Message(role="assistant", content="Done")

    async def strict_stream(**kwargs):
        message = await strict_model(**kwargs)
        yield MessageChunk(**message.model_dump(), is_final=True)

    api.invoke_llm.side_effect = strict_model
    api.invoke_llm_stream = strict_stream
    ctx = make_context(
        config={"model": {"primary": "primary"}, "prompt": prompt, "date-grounding": date_grounding},
        resources=AgentResources(
            models=models,
            tools=tools,
            skills=[SkillResource(skill_name="pdf", description="Work with PDFs")],
        ),
        delivery_supports_streaming=streaming,
    )
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api

    results = [result async for result in runner.run(ctx)]

    assert results[-1].type.value == "run.completed"
    assert len(requests) == 2
    api.call_tool.assert_awaited_once_with(tool_name="event_reply", parameters={})
    for messages in requests:
        system = messages[0]
        content = system.content if isinstance(system.content, str) else "".join(c.text or "" for c in system.content)
        assert content.count("<available_skills>") == 1
        assert "<name>pdf</name>" in content
        assert "Work with PDFs" in content
        assert content.count("platform action tools") == 1
        assert "event_reply" in content
        assert ("Current date:" in content) is date_grounding
        if prompt and prompt[0]["role"] == "system":
            assert content.startswith("Keep this policy.")
            assert system.name == prompt[0].get("name")
        else:
            assert [m.model_dump(exclude_none=True) for m in messages[1 : 1 + len(prompt)]] == prompt
    assert requests[1][-2].tool_calls[0].id == "call-1"
    assert requests[1][-1].role == "tool"
    assert requests[1][-1].tool_call_id == "call-1"
    assert requests[1][-1].content == "Tool finished"
    assert prompt == original


def test_prompt_preserves_empty_message_and_rejects_malformed_content():
    from pkg.messages import build_prompt_messages

    assert build_prompt_messages([{"role": "assistant", "content": ""}]) == [Message(role="assistant", content="")]
    with pytest.raises(ValueError):
        build_prompt_messages([{"role": "system", "content": {"unsupported": "object"}}])


@pytest.mark.asyncio
async def test_explicitly_empty_host_prompt_does_not_resurrect_static_prompt():
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="primary")])
    api.get_prompt.return_value = []
    api.invoke_llm.return_value = Message(role="assistant", content="Answer")
    ctx = make_context(
        config={"model": {"primary": "primary"}, "prompt": [{"role": "system", "content": "REMOVED BY HOST"}]},
        prompt_get=True,
        delivery_supports_streaming=False,
    )
    runner = DefaultRunner()
    runner.get_run_api = lambda context: api
    assert [result async for result in runner.run(ctx)][-1].type.value == "run.completed"
    assert all("REMOVED BY HOST" not in str(m.content) for m in api.invoke_llm.call_args.kwargs["messages"])
