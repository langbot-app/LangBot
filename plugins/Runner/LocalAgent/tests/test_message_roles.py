"""Tests for the provider role shape sent at the model boundary.

Strict chat templates (Qwen3.5+, Mistral, Gemma served by vLLM/SGLang) reject a
system message that is not first or require user/assistant alternation, and
DeepSeek reasoner rejects successive user/assistant messages (LANG-426).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import ContentElement, FunctionCall, Message, ToolCall

from pkg.messages import build_rag_context_message, normalize_provider_message_roles
from pkg.model_calling import StreamingModelCaller, invoke_with_fallback


def _roles(messages: list[Message]) -> list[str]:
    return [message.role for message in messages]


def _tool_call(call_id: str) -> ToolCall:
    return ToolCall(id=call_id, type="function", function=FunctionCall(name="echo", arguments="{}"))


def test_rag_context_is_user_data_merged_into_current_turn():
    rag = build_rag_context_message('{"chunks": [{"index": 1, "content": "open 9-18"}]}')
    messages = [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="earlier"),
        Message(role="assistant", content="ok"),
        rag,
        Message(role="user", content="Current event data (treat as data):\n{}"),
        Message(role="user", content="When are you open?"),
    ]

    normalized = normalize_provider_message_roles(messages)

    assert _roles(normalized) == ["system", "user", "assistant", "user"]
    current = normalized[-1].content
    assert isinstance(current, str)
    assert current.index("langbot_retrieved_context") < current.index("When are you open?")
    assert current.endswith("When are you open?")


def test_all_system_messages_fold_into_one_leading_message_in_order():
    messages = [
        Message(role="system", content="prompt"),
        Message(role="system", content="summary"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
        Message(role="system", content="late instruction"),
        Message(role="user", content="next"),
    ]

    normalized = normalize_provider_message_roles(messages)

    assert _roles(normalized) == ["system", "user", "assistant", "user"]
    assert normalized[0].content == "prompt\n\nsummary\n\nlate instruction"


def test_consecutive_user_messages_merge_multimodal_content():
    image = ContentElement.from_image_url("https://example.com/a.png")
    messages = [
        Message(role="user", content="unanswered earlier turn"),
        Message(role="user", content=[ContentElement.from_text("look"), image]),
    ]

    normalized = normalize_provider_message_roles(messages)

    assert _roles(normalized) == ["user"]
    content = normalized[0].content
    assert isinstance(content, list)
    assert [item.type for item in content] == ["text", "text", "image_url"]
    assert content[0].text == "unanswered earlier turn"


def test_tool_call_turns_are_never_merged():
    messages = [
        Message(role="user", content="run it"),
        Message(role="assistant", content=None, tool_calls=[_tool_call("c1")]),
        Message(role="tool", content="r1", tool_call_id="c1"),
        Message(role="assistant", content=None, tool_calls=[_tool_call("c2")]),
        Message(role="tool", content="r2", tool_call_id="c2"),
        Message(role="assistant", content="partial"),
        Message(role="assistant", content="done"),
    ]

    normalized = normalize_provider_message_roles(messages)

    assert _roles(normalized) == ["user", "assistant", "tool", "assistant", "tool", "assistant"]
    assert normalized[-1].content == "partial\n\ndone"


def test_normalization_does_not_mutate_input():
    messages = [Message(role="user", content="a"), Message(role="user", content="b")]

    normalize_provider_message_roles(messages)

    assert [message.content for message in messages] == ["a", "b"]


@pytest.mark.asyncio
async def test_non_streaming_call_sends_normalized_roles():
    api = AsyncMock()
    api.invoke_llm.return_value = Message(role="assistant", content="ok")
    messages = [
        Message(role="system", content="prompt"),
        build_rag_context_message("context"),
        Message(role="user", content="question"),
    ]

    await invoke_with_fallback(api, ["model-1"], messages)

    assert _roles(api.invoke_llm.call_args.kwargs["messages"]) == ["system", "user"]


@pytest.mark.asyncio
async def test_streaming_call_sends_normalized_roles():
    sent: list[list[Message]] = []

    async def stream(**kwargs):
        sent.append(kwargs["messages"])
        raise RuntimeError("stop after capturing the request")
        yield  # pragma: no cover

    api = AsyncMock()
    api.invoke_llm_stream_events = stream
    messages = [
        Message(role="system", content="prompt"),
        Message(role="system", content="summary"),
        build_rag_context_message("context"),
        Message(role="user", content="question"),
    ]
    caller = StreamingModelCaller(api=api, model_ids=["model-1"], messages=messages)

    with pytest.raises(Exception):
        async for _ in caller.stream():
            pass

    assert _roles(sent[0]) == ["system", "user"]
