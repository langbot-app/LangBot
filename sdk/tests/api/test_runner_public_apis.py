"""Public component access must retain invocation grants and isolation."""

import asyncio

import pytest

from langbot_plugin.api.definition.components.runner import Runner, RunnerContext
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.runner.common import PermissionDeniedError
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action


class Handler:
    def __init__(self):
        self.calls = []

    async def call_action(
        self,
        action,
        data,
        timeout=None,
        action_context=None,
        cancel_peer_on_cancel=False,
    ):
        self.calls.append((action, data))
        await asyncio.sleep(0)
        return {
            Action.CALL_TOOL: {"result": {"ok": True}},
            Action.CALL_PLATFORM_API: {"result": {"mock": True}},
            Action.INVOKE_LLM: {
                "message": {"role": "assistant", "content": data.get("run_id")}
            },
            Action.GET_LLM_MODELS: {"llm_models": ["outside"]},
            Action.HISTORY_PAGE: {"items": [], "has_more": False},
        }.get(action, {})

    async def call_action_generator(self, action, data, timeout=None):
        self.calls.append((action, data))
        yield {"chunk": {"role": "assistant", "content": data["run_id"]}}


def context(name="one"):
    return RunnerContext.model_validate(
        {
            "run_id": name,
            "trigger": {"type": "message.received"},
            "event": {
                "event_id": name,
                "event_type": "message.received",
                "source": "test",
                "data": {},
            },
            "conversation": {"bot_id": "bot"},
            "input": {},
            "delivery": {"surface": "webui"},
            "runtime": {},
            "resources": {
                "models": [{"model_id": name, "operations": ["invoke", "stream"]}],
                "tools": [
                    {
                        "tool_name": "event_reply",
                        "operations": ["call"],
                        "parameters": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                        },
                    },
                    {"tool_name": "read-only", "operations": ["detail"]},
                ],
            },
        }
    )


def component(fn):
    runner = Runner()
    handler = Handler()
    runner.bind_runtime(plugin_runtime_handler=handler)
    runner.plugin = LangBotAPIProxy(handler)
    runner.run = fn
    return runner, handler


async def test_shared_plugin_api_is_bound_per_concurrent_run_and_restored():
    seen = []

    async def run(ctx):
        seen.append((ctx.run_id, await runner.plugin.get_llm_models()))
        result = await runner.plugin.invoke_llm(
            ctx.run_id, [Message(role="user", content="hi")]
        )
        assert result.content == ctx.run_id
        await runner.plugin.call_tool("event_reply", {"text": ctx.run_id})
        with pytest.raises(PermissionDeniedError):
            await runner.plugin.invoke_llm("outside", [])
        with pytest.raises(PermissionDeniedError):
            await runner.plugin.call_tool("disabled", {})

    runner, handler = component(run)

    async def collect(name):
        return [item async for item in runner.invoke(context(name))]

    results = await asyncio.gather(collect("one"), collect("two"))
    assert sorted(seen) == [("one", ["one"]), ("two", ["two"])]
    assert {data["run_id"] for _, data in handler.calls} == {"one", "two"}
    assert all(
        len([r for r in result if r.type == "tool.call.completed"]) == 2
        for result in results
    )
    assert await runner.plugin.get_llm_models() == ["outside"]


async def test_context_tool_list_excludes_disabled_operations_and_cannot_mutate_grants():
    async def run(ctx):
        first = await ctx.get_available_tools()
        assert [t["name"] for t in first] == ["event_reply"]
        assert first[0]["parameters"]["properties"]["text"]["type"] == "string"
        first[0]["parameters"].clear()
        first[0]["name"] = "injected"
        ctx.resources.tools.clear()
        assert (await ctx.get_available_tools())[0]["name"] == "event_reply"
        assert (await runner.plugin.list_tools())[0]["parameters"]["type"] == "object"
        assert await ctx.get_bot_uuid() == "bot"
        await ctx.call_tool("event_reply", {"text": "hi"})

    runner, handler = component(run)
    assert [item async for item in runner.invoke(context())][-1].type == "run.completed"
    assert len(handler.calls) == 1


async def test_platform_api_and_rich_reply_carry_run_and_trace():
    chain = MessageChain([Plain(text="hi")])

    async def run(ctx):
        await runner.plugin.send_message(
            await ctx.get_bot_uuid(), "group", "group", chain
        )
        await runner.plugin.call_platform_api(
            "bot", "get_group_info", {"group_id": "group"}
        )
        await ctx.reply(chain, quote_origin=True)

    runner, handler = component(run)
    items = [item async for item in runner.invoke(context())]
    assert len([item for item in items if item.type == "tool.call.completed"]) == 3
    assert all(data["run_id"] == "one" for _, data in handler.calls)
    assert handler.calls[-1][1]["context_tool"] == "event_reply"
    assert handler.calls[-1][1]["params"]["quote_origin"] is True


async def test_background_task_cannot_fall_back_to_unscoped_api_after_run():
    gate = asyncio.Event()
    tasks = []

    async def run(ctx):
        async def later():
            await gate.wait()
            await runner.plugin.get_llm_models()

        tasks.append(asyncio.create_task(later()))

    runner, handler = component(run)
    _ = [item async for item in runner.invoke(context())]
    gate.set()
    with pytest.raises(RuntimeError, match="ended"):
        await tasks[0]
    assert handler.calls == []


async def test_stream_and_context_methods_reuse_the_run_contract():
    async def run(ctx):
        chunks = [
            chunk async for chunk in runner.plugin.invoke_llm_stream(ctx.run_id, [])
        ]
        assert chunks[0].content == ctx.run_id
        assert (await ctx.history_page()).items == []

    runner, handler = component(run)
    ctx = context()
    ctx.context.available_apis.history_page = True
    _ = [item async for item in runner.invoke(ctx)]
    assert all(data["run_id"] == "one" for _, data in handler.calls)
