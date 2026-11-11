import asyncio
import contextlib

import pytest

from langbot_plugin.entities.io.actions.enums import ActionType, CommonAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.entities.io.errors import (
    ActionCallError,
    ActionCallTimeoutError,
    ConnectionClosedError,
)
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.handler import (
    Handler,
    STREAM_WINDOW,
    MAX_STREAM_FRAME_BYTES,
    _StreamQueue,
)
from tests.helpers.protocol import ProtocolConnection


class Action(ActionType):
    STREAM = "test_stream"
    ECHO = "test_echo"


class LinkedConnection(ProtocolConnection):
    async def send(self, message):
        await super().send(message)
        await self.peer.incoming.put(message)


@contextlib.asynccontextmanager
async def pair():
    left, right = LinkedConnection(), LinkedConnection()
    left.peer, right.peer = right, left
    consumer, producer = Handler(left), Handler(right)
    tasks = [asyncio.create_task(consumer.run()), asyncio.create_task(producer.run())]
    try:
        yield consumer, producer
    finally:
        await consumer._cancel_action_tasks()
        await producer._cancel_action_tasks()
        await left.incoming.put(ConnectionClosedError("closed"))
        await right.incoming.put(ConnectionClosedError("closed"))
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_slow_stream_is_bounded_and_does_not_block_other_calls():
    async with pair() as (consumer, producer):
        produced = 0

        @producer.action(Action.STREAM)
        async def produce(data):
            nonlocal produced
            for i in range(300):
                produced += 1
                yield ActionResponse.success(
                    {"index": i, "text": "你好", "reasoning": str(i), "arguments": "{"}
                )

        @producer.action(Action.ECHO)
        async def echo(data):
            return ActionResponse.success(data)

        stream = consumer.call_action_generator(Action.STREAM, {}, timeout=2)
        values = [await anext(stream)]
        await asyncio.sleep(0.1)
        assert produced == STREAM_WINDOW
        assert await consumer.call_action(Action.ECHO, {"alive": True}, timeout=1) == {
            "alive": True
        }
        async for value in stream:
            values.append(value)
            await asyncio.sleep(0.001)
        assert values == [
            {"index": i, "text": "你好", "reasoning": str(i), "arguments": "{"}
            for i in range(300)
        ]
        assert consumer.resp_queues == {}
        assert producer._stream_senders == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["close", "cancel", "timeout", "oversize"])
async def test_failed_or_closed_consumer_closes_provider(mode):
    async with pair() as (consumer, producer):
        closed = asyncio.Event()

        @producer.action(Action.STREAM)
        async def stream(data):
            try:
                if mode == "oversize":
                    yield ActionResponse.success({"text": "x" * MAX_STREAM_FRAME_BYTES})
                else:
                    yield ActionResponse.success({"first": True})
                    await asyncio.Event().wait()
            finally:
                closed.set()

        output = consumer.call_action_generator(Action.STREAM, {}, timeout=0.05)
        if mode == "oversize":
            with pytest.raises(ActionCallError, match="byte limit"):
                await anext(output)
        else:
            assert await anext(output) == {"first": True}
            if mode == "close":
                await output.aclose()
            elif mode == "timeout":
                with pytest.raises(ActionCallTimeoutError):
                    await anext(output)
            else:
                pending = asyncio.create_task(anext(output))
                await asyncio.sleep(0.01)
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
        await asyncio.wait_for(closed.wait(), 1)
        assert consumer.resp_queues == {}


@pytest.mark.asyncio
async def test_ack_cannot_release_another_workspace_stream():
    async with pair() as (consumer, producer):
        context = ActionContext(
            instance_uuid="instance", workspace_uuid="a", placement_generation=1
        )
        other = ActionContext(
            instance_uuid="instance", workspace_uuid="b", placement_generation=1
        )

        @producer.action(Action.STREAM)
        async def stream(data):
            for i in range(100):
                yield ActionResponse.success({"index": i})

        output = consumer.call_action_generator(
            Action.STREAM, {}, action_context=context
        )
        await anext(output)
        await asyncio.sleep(0.05)
        seq, sender = next(iter(producer._stream_senders.items()))
        result = await consumer.call_action(
            CommonAction.STREAM_ACK, {"seq_id": seq, "index": 8}, action_context=other
        )
        assert result == {"accepted": False}
        assert sender.acknowledged == 0
        with pytest.raises(ActionCallError, match="Invalid stream acknowledgement"):
            await consumer.call_action(
                CommonAction.STREAM_ACK,
                {"seq_id": seq, "index": 100},
                action_context=context,
            )
        await output.aclose()


def test_legacy_stream_byte_limit_and_queue_release():
    queue = _StreamQueue()
    for _ in range(STREAM_WINDOW):
        queue.put_response(ActionResponse.success({}), MAX_STREAM_FRAME_BYTES)
    with pytest.raises(asyncio.QueueFull):
        queue.put_response(ActionResponse.success({}), 1)
    for _ in range(STREAM_WINDOW):
        queue.get_nowait()
    assert queue.buffer_bytes == 0


@pytest.mark.asyncio
async def test_concurrent_streams_have_independent_credits():
    async with pair() as (consumer, producer):

        @producer.action(Action.STREAM)
        async def stream(data):
            for i in range(40):
                yield ActionResponse.success({"id": data["id"], "index": i})

        async def consume(index):
            return [
                item
                async for item in consumer.call_action_generator(
                    Action.STREAM, {"id": index}, timeout=5
                )
            ]

        values = await asyncio.wait_for(
            asyncio.gather(*(consume(i) for i in range(32))), 10
        )
        for index, items in enumerate(values):
            assert items == [{"id": index, "index": i} for i in range(40)]


@pytest.mark.asyncio
async def test_legacy_overflow_cancels_upstream_before_consumer_resumes():
    async with pair() as (consumer, producer):
        original = producer._handle_action

        async def legacy(request, **kwargs):
            request.pop("stream_flow_control", None)
            await original(request, **kwargs)

        producer._handle_action = legacy
        closed = asyncio.Event()

        @producer.action(Action.STREAM)
        async def produce(data):
            try:
                while True:
                    yield ActionResponse.success({"text": "chunk"})
            finally:
                closed.set()

        output = consumer.call_action_generator(Action.STREAM, {}, timeout=2)
        await anext(output)
        # The consumer is deliberately paused, so only routing can stop the
        # legacy producer after the bounded buffer fills.
        await asyncio.wait_for(closed.wait(), 2)
        with pytest.raises(ActionCallError, match="buffer full"):
            await anext(output)
        assert not consumer._stream_cancellations
