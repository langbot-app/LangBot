"""Run-local token counts retain provider semantics without duplicate Host RPCs."""

from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner.resources import ModelResource

from pkg.context_pipeline import ContextTokenCounterRequiredError, HostContextTokenCounter
from pkg.run_assembly import AgentRunAssembler
from tests.test_runner import FakeRunnerAPIProxy, make_context


@pytest.mark.asyncio
async def test_empty_input_keeps_provider_count_and_reuse_is_run_local():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(return_value=7)
    counter = HostContextTokenCounter(api, "model-1")

    assert await counter.count([]) == 7
    assert await counter.count([]) == 7
    api.count_tokens.assert_awaited_once_with(
        llm_model_uuid="model-1", messages=[], funcs=[], reasoning_level="provider_default"
    )

    assert await HostContextTokenCounter(api, "model-1").count([]) == 7
    assert api.count_tokens.await_count == 2


@pytest.mark.asyncio
async def test_count_reuse_tracks_message_content_model_and_reasoning():
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=[11, 12, 13, 14, 15])
    counter = HostContextTokenCounter(api, "model-1")
    message = Message(role="user", content="original")

    assert await counter.count([message]) == 11
    assert await counter.count([message.model_copy(deep=True)]) == 11
    message.content = "changed"
    assert await counter.count([message]) == 12
    message.provider_specific_fields = {"signature": "changed"}
    assert await counter.count([message]) == 13
    counter.model_id = "model-2"
    assert await counter.count([message]) == 14
    counter.reasoning_level = "high"
    assert await counter.count([message]) == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [True, -1, "7", RuntimeError("Host unavailable")])
async def test_failed_or_invalid_counts_are_not_reused(failure):
    api = FakeRunnerAPIProxy()
    api.count_tokens = AsyncMock(side_effect=[failure, 9])
    counter = HostContextTokenCounter(api, "model-1")

    with pytest.raises((ContextTokenCounterRequiredError, RuntimeError)):
        await counter.count([])
    assert await counter.count([]) == 9
    assert api.count_tokens.await_count == 2


@pytest.mark.asyncio
async def test_initial_assembly_and_model_hook_share_counts():
    api = FakeRunnerAPIProxy(models=[ModelResource(model_id="model-1")])
    context = make_context(
        config={
            "model": {"primary": "model-1"},
            "prompt": [{"role": "system", "content": "Keep the sentinel"}],
            "date-grounding": False,
        },
        input_text="request sentinel",
    )
    assembly = await AgentRunAssembler(api, context).assemble()
    prepared = await assembly.hooks.prepare_model_turn(assembly.messages)

    assert [(message.role, message.content) for message in prepared] == [
        ("system", "Keep the sentinel"),
        ("user", "request sentinel"),
    ]
    assert api.count_tokens.await_count <= 4
    assert any(call.kwargs["messages"] == [] for call in api.count_tokens.await_args_list)
