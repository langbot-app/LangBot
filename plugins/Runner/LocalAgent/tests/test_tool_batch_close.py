import asyncio

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message

from pkg.agent_core.langbot import LangBotToolExecutor
from pkg.agent_core.loop import AgentLoop
from pkg.agent_core.types import AgentLoopEventType, ModelTurnEvent, ModelTurnResult, ToolCallRequest


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_close_after_first_tool_result_awaits_remaining_tasks(streaming):
    calls = [ToolCallRequest(id=name, name=name, arguments="{}") for name in ("fast", "slow")]

    class Model:
        async def invoke_turn(self, **kwargs):
            return ModelTurnResult(
                message=Message(role="assistant", content="tools", tool_calls=[c.to_tool_call() for c in calls]),
                tool_calls=calls,
                committed_model_id="model",
            )

        async def stream_turn(self, **kwargs):
            yield ModelTurnEvent.message_end(await self.invoke_turn())

    class API:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.closed = False
            self.side_effects = []

        async def call_tool(self, *, tool_name, parameters):
            if tool_name == "fast":
                await self.started.wait()
                return "fast"
            self.started.set()
            try:
                await self.release.wait()
                self.side_effects.append("late")
                return "slow"
            finally:
                self.closed = True

    api = API()
    loop = AgentLoop(
        model_adapter=Model(),
        tool_executor=LangBotToolExecutor(api, {"fast", "slow"}),
        model_ids=["model"],
        messages=[],
        tools=[],
        streaming=streaming,
        max_tool_iterations=2,
    )
    stream = loop.run()
    try:
        async with asyncio.timeout(2):
            async for event in stream:
                if event.type == AgentLoopEventType.TOOL_EXECUTION_END:
                    break
            await stream.aclose()
        assert api.closed
        api.release.set()
        await asyncio.sleep(0)
        assert api.side_effects == []
    finally:
        await stream.aclose()
        api.release.set()
