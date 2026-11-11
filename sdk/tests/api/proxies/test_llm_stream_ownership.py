"""Every public stream wrapper must close its immediate upstream on exit."""

import asyncio
from contextlib import nullcontext

import pytest

from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from tests.api.test_runner_public_apis import context


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["plugin", "runner", "bound-plugin"])
@pytest.mark.parametrize("method", ["invoke_llm_stream", "invoke_llm_stream_events"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_close_propagates_without_waiting_for_gc(surface, method, cancel):
    closed = []
    waiting = asyncio.Event()

    class Transport:
        async def call_action_generator(self, action, data, timeout=None):
            try:
                yield {"chunk": {"role": "assistant", "content": "first"}}
                waiting.set()
                await asyncio.Event().wait()
            finally:
                closed.append(data.get("run_id"))

    transport = Transport()
    runner = RunnerAPIProxy(ctx=context(), plugin_runtime_handler=transport)
    proxy = runner if surface == "runner" else LangBotAPIProxy(transport)
    scope = (
        bind_invocation(transport, runner)
        if surface == "bound-plugin"
        else nullcontext()
    )
    with scope:
        stream = getattr(proxy, method)("one", [])
        await anext(stream)
        if cancel:
            pending = asyncio.create_task(anext(stream))
            await waiting.wait()
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        await stream.aclose()
        assert closed == [None if surface == "plugin" else "one"]
