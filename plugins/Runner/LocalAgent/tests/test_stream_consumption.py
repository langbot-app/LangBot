import asyncio
from types import SimpleNamespace

import pytest
from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, MessageChunk, ToolCall

from pkg.model_calling import StreamingModelCaller


@pytest.mark.asyncio
async def test_fast_stream_coalesces_without_losing_text_reasoning_or_arguments(monkeypatch):
    monkeypatch.setattr("pkg.model_calling.time.monotonic", lambda: 1.0)

    async def provider(**kwargs):
        for i in range(1000):
            yield MessageChunk(
                role="assistant",
                content="字",
                provider_specific_fields={"reasoning_content": "想"},
                tool_calls=[ToolCall(id="call", type="function", function=FunctionCall(name="tool", arguments="a"))],
                is_final=i == 999,
            )

    caller = StreamingModelCaller(SimpleNamespace(invoke_llm_stream=provider), ["model"], [])
    values = [chunk async for chunk, _ in caller.stream() if chunk.content]
    assert len(values) == 2
    assert values[-1].content == "字" * 1000
    assert values[-1].provider_specific_fields["reasoning_content"] == "想" * 1000
    assert values[-1].tool_calls[0].function.arguments == "a" * 1000


@pytest.mark.asyncio
async def test_close_after_first_snapshot_closes_underlying_provider():
    closed = asyncio.Event()

    async def provider(**kwargs):
        try:
            yield MessageChunk(role="assistant", content="first")
            await asyncio.Event().wait()
        finally:
            closed.set()

    caller = StreamingModelCaller(SimpleNamespace(invoke_llm_stream=provider), ["model"], [])
    stream = caller.stream()
    await anext(stream)
    await stream.aclose()
    assert closed.is_set()
