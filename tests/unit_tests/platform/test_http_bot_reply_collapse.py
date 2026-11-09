"""Regression tests for http_bot reply collection (LANG-370).

The pipeline streams to http_bot: every ``reply_message_chunk`` carries the
accumulated content of one reply (chunks of a reply share ``resp_message_id``).
/sync must return each reply once, and callback mode must keep one final
callback per reply with monotonically increasing sequences.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
import quart
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from langbot.pkg.platform.sources.http_bot import HttpBotAdapter


def make_adapter():
    return HttpBotAdapter(
        config={'signature_required': False, 'callback_timeout': 1},
        logger=AsyncMock(spec=AbstractEventLogger),
    )


def inbound(adapter, session_id='s-1'):
    event, _, _, message_id = adapter._build_event(
        {'session_id': session_id, 'message': [{'type': 'Plain', 'text': 'plain hello'}]}
    )
    return event, message_id


def chunk(resp_id, text, *, is_final, tool_calls=None):
    return provider_message.MessageChunk(
        role='assistant',
        content=text,
        all_content=text,
        resp_message_id=resp_id,
        is_final=is_final,
        tool_calls=tool_calls,
    )


async def stream_reply(adapter, event, resp_id, snapshots):
    """Deliver one reply the way the chat handler + respback stage do."""
    for index, text in enumerate(snapshots):
        is_final = index == len(snapshots) - 1
        await adapter.reply_message_chunk(
            message_source=event,
            bot_message=chunk(resp_id, text, is_final=is_final),
            message=message.MessageChain([message.Plain(text=text)]),
            is_final=is_final,
        )


async def run_sync(adapter, listener, session_id='s-1'):
    event, message_id = inbound(adapter, session_id)
    app = quart.Quart(__name__)
    async with app.app_context():
        response, status = await asyncio.wait_for(adapter._run_sync(event, listener, session_id, message_id), 2)
        assert status == 200
        return (await response.get_json())['data']['message']


def texts(parts):
    return [part['text'] for part in parts]


@pytest.mark.asyncio
async def test_sync_returns_a_streamed_reply_once():
    adapter = make_adapter()
    adapter._enqueue_callback = AsyncMock(side_effect=AssertionError('sync reply must not use callback'))

    async def listener(event, live_adapter):
        # A Runner delta followed by its completed message (Dify, n8n, ...).
        await stream_reply(live_adapter, event, 'r1', ['Hello there', 'Hello there'])

    assert texts(await run_sync(adapter, listener)) == ['Hello there']


@pytest.mark.asyncio
async def test_sync_keeps_latest_snapshot_and_every_distinct_reply_in_order():
    adapter = make_adapter()

    async def listener(event, live_adapter):
        await stream_reply(live_adapter, event, 'r1', ['Check', 'Checking logs', 'Checking logs…'])
        await stream_reply(live_adapter, event, 'r2', ['Fixed', 'Fixed — retry.'])
        await live_adapter.reply_message(event, message.MessageChain([message.Plain(text='notice')]))

    assert texts(await run_sync(adapter, listener)) == ['Checking logs…', 'Fixed — retry.', 'notice']


@pytest.mark.asyncio
async def test_sync_does_not_merge_identical_distinct_replies():
    adapter = make_adapter()

    async def listener(event, live_adapter):
        await stream_reply(live_adapter, event, 'r1', ['ok'])
        await stream_reply(live_adapter, event, 'r2', ['ok'])

    assert texts(await run_sync(adapter, listener)) == ['ok', 'ok']


@pytest.mark.asyncio
async def test_sync_tool_round_stays_one_reply():
    adapter = make_adapter()

    async def listener(event, live_adapter):
        tool_call = provider_message.ToolCall(
            id='call-1', type='function', function=provider_message.FunctionCall(name='f', arguments='{}')
        )
        await live_adapter.reply_message_chunk(
            message_source=event,
            bot_message=chunk('r1', 'Looking', is_final=False, tool_calls=[tool_call]),
            message=message.MessageChain([message.Plain(text='Looking')]),
            is_final=False,
        )
        await stream_reply(live_adapter, event, 'r1', ['Looking… done', 'Looking… done'])

    assert texts(await run_sync(adapter, listener)) == ['Looking… done']


@pytest.mark.asyncio
async def test_callback_mode_sends_one_final_per_reply_with_ordered_sequences():
    adapter = make_adapter()
    adapter._enqueue_callback = AsyncMock()
    event, message_id = inbound(adapter)

    await stream_reply(adapter, event, 'r1', ['Hel', 'Hello', 'Hello'])

    payloads = [call.args[1] for call in adapter._enqueue_callback.await_args_list]
    assert [p['sequence'] for p in payloads] == [1, 2, 3]
    assert [p['is_final'] for p in payloads] == [False, False, True]
    assert all(p['stream'] and p['reply_to'] == message_id for p in payloads)
    assert texts(payloads[-1]['message']) == ['Hello']

    # The next turn restarts the sequence after the final callback.
    adapter._enqueue_callback.reset_mock()
    await stream_reply(adapter, event, 'r2', ['Again'])
    payload = adapter._enqueue_callback.await_args.args[1]
    assert (payload['sequence'], payload['is_final']) == (1, True)


@pytest.mark.asyncio
async def test_sync_collapses_agent_reply_stream_update_and_finish():
    """Agent bindings stream a Runner delta as ``update`` and the completed message as ``finish``."""
    from types import SimpleNamespace
    from uuid import uuid4

    from langbot.pkg.agent.runner.reply_stream import ReplyStreamRequest, ReplyStreamSession

    adapter = make_adapter()
    adapter._enqueue_callback = AsyncMock(side_effect=AssertionError('sync reply must not use callback'))
    delivery = SimpleNamespace(reply_target={}, surface='http_bot', platform_capabilities={})

    async def listener(event, live_adapter):
        streams = ReplyStreamSession(SimpleNamespace(delivery=delivery), live_adapter, event)
        stream_id = uuid4()
        await streams.apply(ReplyStreamRequest(stream_id=stream_id, operation='update', text='echo: plain'))
        await streams.apply(ReplyStreamRequest(stream_id=stream_id, operation='update', text='echo: plain hello'))
        await streams.apply(ReplyStreamRequest(stream_id=stream_id, operation='finish', text='echo: plain hello'))
        await streams.close()

    assert texts(await run_sync(adapter, listener)) == ['echo: plain hello']
