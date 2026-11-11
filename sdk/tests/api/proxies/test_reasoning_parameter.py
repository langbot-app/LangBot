"""Backward-compatible optional reasoning across ordinary and Runner calls."""

import inspect

import pytest

from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from tests.api.proxies.test_langbot_api import FakeHandler
from tests.api.test_runner_public_apis import context, component

METHODS = [
    "invoke_llm",
    "invoke_llm_with_usage",
    "invoke_llm_stream",
    "invoke_llm_stream_events",
]


def handler(features=True):
    return FakeHandler(
        {
            Action.GET_LANGBOT_VERSION: {
                "version": "test",
                **({"api_features": ["llm.reasoning_level"]} if features else {}),
            },
            Action.INVOKE_LLM: {"message": {"role": "assistant", "content": "ok"}},
            Action.INVOKE_LLM_STREAM: [
                {"chunk": {"role": "assistant", "content": "ok"}}
            ],
            Action.COUNT_TOKENS: {"tokens": 10},
        }
    )


async def invoke(proxy, method, **kwargs):
    result = getattr(proxy, method)("one", [], **kwargs)
    if inspect.isasyncgen(result):
        return [value async for value in result]
    return await result


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("runner", [False, True])
async def test_optional_parameter_preserves_old_wire_and_explicit_options(
    method, runner
):
    transport = handler()
    proxy = (
        RunnerAPIProxy(ctx=context(), plugin_runtime_handler=transport)
        if runner
        else LangBotAPIProxy(transport)
    )
    await invoke(proxy, method, extra_args={"temperature": 0.5})
    assert len(transport.calls) == 1
    assert "reasoning_level" not in transport.calls[-1][1]
    await invoke(proxy, method, reasoning_level="medium")
    assert transport.calls[-1][1]["reasoning_level"] == "medium"
    if runner:
        assert transport.calls[-1][1]["run_id"] == "one"
    await invoke(proxy, method, reasoning_level="provider_default")
    assert transport.calls[-1][1]["reasoning_level"] == "provider_default"
    assert (
        sum(action == Action.GET_LANGBOT_VERSION for action, _, _ in transport.calls)
        == 1
    )
    assert (
        inspect.signature(getattr(proxy, method)).parameters["reasoning_level"].kind
        == inspect.Parameter.KEYWORD_ONLY
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_explicit_option_fails_before_model_call_on_old_host(method):
    transport = handler(False)
    proxy = LangBotAPIProxy(transport)
    with pytest.raises(RuntimeError, match="upgrade LangBot"):
        await invoke(proxy, method, reasoning_level="high")
    assert [action for action, _, _ in transport.calls] == [Action.GET_LANGBOT_VERSION]
    # Omitting the new option still works on that same Host.
    await invoke(proxy, method)


@pytest.mark.asyncio
async def test_invalid_option_is_rejected_without_rpc():
    transport = handler()
    with pytest.raises(ValueError, match="reasoning level"):
        await invoke(
            LangBotAPIProxy(transport), "invoke_llm", reasoning_level="secret-invalid"
        )
    assert not transport.calls


@pytest.mark.asyncio
async def test_runner_count_tokens_uses_same_option():
    transport = handler()
    ctx = context()
    ctx.resources.models[0].operations.append("count_tokens")
    proxy = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=transport)
    assert await invoke(proxy, "count_tokens", reasoning_level="low") == 10
    assert transport.calls[-1][1]["reasoning_level"] == "low"


@pytest.mark.asyncio
async def test_public_plugin_method_retains_runner_scope_with_explicit_level():
    async def run(ctx):
        await runner.plugin.invoke_llm("one", [], reasoning_level="high")
        if False:
            yield

    runner, transport = component(run)
    original = transport.call_action

    async def call(
        action, data, timeout=None, action_context=None, cancel_peer_on_cancel=False
    ):
        if action == Action.GET_LANGBOT_VERSION:
            return {"api_features": ["llm.reasoning_level"]}
        return await original(
            action,
            data,
            timeout,
            action_context=action_context,
            cancel_peer_on_cancel=cancel_peer_on_cancel,
        )

    transport.call_action = call
    _ = [result async for result in runner.invoke(context())]
    assert transport.calls[-1][1]["run_id"] == "one"
    assert transport.calls[-1][1]["reasoning_level"] == "high"


@pytest.mark.asyncio
async def test_legacy_positional_call_and_overridden_usage_method_keep_working():
    from langbot_plugin.api.entities.builtin.provider.message import (
        LLMInvokeResult,
        Message,
    )

    class LegacyProxy(LangBotAPIProxy):
        async def invoke_llm_with_usage(
            self, llm_model_uuid, messages, funcs=[], extra_args={}, timeout=None
        ):
            assert llm_model_uuid == "one"
            assert extra_args == {"temperature": 0.2}
            assert timeout == 37
            return LLMInvokeResult(message=Message(role="assistant", content="legacy"))

    proxy = LegacyProxy(handler(False))
    result = await proxy.invoke_llm("one", [], [], {"temperature": 0.2}, 37)
    assert result.content == "legacy"
