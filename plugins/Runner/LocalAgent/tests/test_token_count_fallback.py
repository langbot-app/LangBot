"""Counting failures must not abort text-only agent turns."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import ContentElement, Message
from langbot_plugin.api.entities.builtin.runner.resources import ModelResource

from pkg import context_pipeline
from pkg.context_pipeline import (
    ContextBudget,
    ContextCompactor,
    ContextTokenCounterRequiredError,
    HostContextTokenCounter,
)
from pkg.run_assembly import AgentRunAssembler
from tests.test_runner import FakeRunnerAPIProxy, make_context


@pytest.mark.asyncio
async def test_count_failure_continues_assembly_and_model_turn(caplog):
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="model-1")])
    api.count_tokens = AsyncMock(side_effect=RuntimeError("tokenizer unavailable"))
    ctx = make_context(config={"model": {"primary": "model-1"}, "date-grounding": False}, input_text="你好 hello")
    assembly = await AgentRunAssembler(api, ctx).assemble()
    prepared = await assembly.hooks.prepare_model_turn(assembly.messages)
    assert prepared[-1].content == "你好 hello"
    assert api.count_tokens.await_count == 1
    assert "conservative" in caplog.text


@pytest.mark.asyncio
async def test_timeout_is_bounded_and_not_repeated(monkeypatch):
    monkeypatch.setattr(context_pipeline, "HOST_TOKEN_COUNT_TIMEOUT", 0.01)
    api = FakeRunnerAPIProxy()

    async def stalled(**kwargs):
        await asyncio.Event().wait()

    api.count_tokens = AsyncMock(side_effect=stalled)
    counter = HostContextTokenCounter(api, "model-1")
    assert await asyncio.wait_for(counter.count([Message(role="user", content="hello")]), 0.5) > 0
    assert await counter.count([Message(role="user", content="different")]) > 0
    assert api.count_tokens.await_count == 1


@pytest.mark.asyncio
async def test_fallback_includes_utf8_and_tools():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=ValueError("bad count"))
    text = "你好🙂" * 100
    tools = [{"name": "search", "description": "schema " * 200}]
    counter = HostContextTokenCounter(api, "model-1", tools)
    tokens = await counter.count([Message(role="user", content=text)])
    assert tokens >= len(text.encode()) + len(tools[0]["description"].encode())


@pytest.mark.asyncio
async def test_media_failure_does_not_underestimate_unknown_size():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=ValueError("bad count"))
    counter = HostContextTokenCounter(api, "model-1")
    with pytest.raises(ContextTokenCounterRequiredError, match="media"):
        await counter.count(
            [Message(role="user", content=[ContentElement.from_image_url("https://example.com/image")])]
        )


@pytest.mark.asyncio
async def test_cancellation_propagates():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await HostContextTokenCounter(api, "model-1").count([])


@pytest.mark.asyncio
async def test_fallback_compacts_history_within_budget():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=RuntimeError("unavailable"))
    counter = HostContextTokenCounter(api, "model-1")
    budget = ContextBudget(window_tokens=3000, reserve_tokens=500, keep_recent_tokens=200, summary_tokens=200)
    assembly = await ContextCompactor(budget, token_counter=counter).compact_async(
        prompt_messages=[],
        history_messages=[Message(role="user", content="你好🙂" * 1000)],
        current_messages=[Message(role="user", content="keep current")],
    )
    assert assembly.messages[-1].content == "keep current"
    assert assembly.tokens_after <= budget.input_tokens
    assert await counter.count(assembly.messages) == assembly.tokens_after


@pytest.mark.asyncio
async def test_unshrinkable_tool_schemas_fail_closed():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=RuntimeError("unavailable"))
    counter = HostContextTokenCounter(api, "model-1", [{"name": "search", "description": "schema" * 1000}])
    with pytest.raises(ContextTokenCounterRequiredError, match="exceeds"):
        await ContextCompactor(
            ContextBudget(window_tokens=1000, reserve_tokens=100), token_counter=counter
        ).compact_async(
            prompt_messages=[], history_messages=[], current_messages=[Message(role="user", content="hello")]
        )
