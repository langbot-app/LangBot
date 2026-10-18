"""Regression tests for WeCom AI Bot streaming chunks with blank content.

A blank *final* snapshot used to be forwarded to the client as-is. On WeCom the
stream frame replaces the displayed bubble, so this closed the stream with an
empty bubble and stranded the model's real answer in a separate ``reply_text``
message (observed as "empty message, then the real reply").

These tests lock in the fixed behaviour:

* blank snapshots are never sent, final or not;
* a blank final snapshot does not close the stream session, so a following
  non-blank chunk can still finalize it;
* a blank final snapshot with earlier content still finalizes with that
  content (the previous-content fallback keeps it non-blank).
"""

import pytest

import langbot.pkg.core.app  # noqa: F401
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient


class Logger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    async def warning(self, message):
        self.warnings.append(message)

    async def error(self, message):
        self.errors.append(message)

    async def info(self, message):
        return None


class RecordingClient(WecomBotWsClient):
    """A client that records reply frames instead of touching a socket."""

    def __init__(self):
        super().__init__(bot_id='bot', secret='secret', logger=Logger())
        self.replies = []

    async def _send_reply(self, req_id, body, cmd='aibot_respond_msg'):
        self.replies.append((cmd, req_id, body))
        return {'errcode': 0}

    def seed_stream(self, msg_id='msg-1'):
        self._stream_ids[msg_id] = 'req-1|stream-1'
        self._stream_sessions[msg_id] = {
            'req_id': 'req-1',
            'stream_id': 'stream-1',
            'msg_id': msg_id,
            'user_id': 'user-1',
            'chat_id': 'chat-1',
            'chat_type': 'single',
        }

    def stream_still_open(self, msg_id='msg-1'):
        return msg_id in self._stream_ids

    def stream_frames(self):
        return [body for _cmd, _req, body in self.replies if body.get('msgtype') == 'stream']


@pytest.mark.asyncio
async def test_blank_final_chunk_does_not_close_stream():
    client = RecordingClient()
    client.seed_stream()

    ok = await client.push_stream_chunk('msg-1', '', is_final=True)

    assert ok is True
    assert client.stream_frames() == []
    assert client.stream_still_open()


@pytest.mark.asyncio
async def test_blank_non_final_chunk_is_skipped():
    client = RecordingClient()
    client.seed_stream()

    ok = await client.push_stream_chunk('msg-1', '   \u200b', is_final=False)

    assert ok is True
    assert client.stream_frames() == []
    assert client.stream_still_open()


@pytest.mark.asyncio
async def test_blank_final_after_content_finalizes_with_previous_content():
    client = RecordingClient()
    client.seed_stream()

    await client.push_stream_chunk('msg-1', 'hello', is_final=False)
    ok = await client.push_stream_chunk('msg-1', '', is_final=True)

    frames = client.stream_frames()
    assert ok is True
    assert len(frames) == 2
    assert frames[-1]['stream']['content'] == 'hello'
    assert frames[-1]['stream']['finish'] is True
    assert not client.stream_still_open()


@pytest.mark.asyncio
async def test_real_final_chunk_is_sent_and_closes_stream():
    client = RecordingClient()
    client.seed_stream()

    ok = await client.push_stream_chunk('msg-1', 'the answer', is_final=True)

    frames = client.stream_frames()
    assert ok is True
    assert len(frames) == 1
    assert frames[-1]['stream']['content'] == 'the answer'
    assert frames[-1]['stream']['finish'] is True
    assert not client.stream_still_open()


@pytest.mark.asyncio
async def test_duplicate_final_is_acknowledged_without_sending_again():
    client = RecordingClient()
    client.seed_stream()
    assert await client.push_stream_chunk('msg-1', 'answer', is_final=True)
    assert await client.push_stream_chunk('msg-1', 'answer', is_final=True)
    assert len(client.stream_frames()) == 1
    assert not await client.push_stream_chunk('different-message', 'answer', is_final=True)
    assert not await client.push_stream_chunk('msg-1', 'different answer', is_final=True)


@pytest.mark.asyncio
async def test_runner_cumulative_snapshots_reach_wire_once_without_concatenation():
    from langbot.pkg.pipeline.process.stream_results import coalesce_stream_results
    from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
    from tests.unit_tests.platform.test_wecombot_eba_adapter import (
        make_adapter,
        wecombot_event,
        WecomBotEventConverter,
    )

    client = RecordingClient()
    client.seed_stream()
    adapter = make_adapter()
    adapter.bot = client
    event = await WecomBotEventConverter().target2yiri(wecombot_event())
    snapshots = ['<think>test', '<think>test</think>\nOK', '<think>test</think>\nOK!']

    async def runner():
        # LocalAgent's StreamingModelCaller sets content to the accumulated
        # text, leaves all_content unset, then emits message.completed.
        for index, text in enumerate(snapshots):
            yield MessageChunk(role='assistant', content=text, msg_sequence=index + 1, is_final=index == 2)
        yield Message(role='assistant', content=snapshots[-1])

    async for result in coalesce_stream_results(runner()):
        final = isinstance(result, Message) or result.is_final
        if isinstance(result, MessageChunk):
            result = result.model_copy(update={'content': result.all_content})
        await adapter.reply_message_chunk(event, result, result.get_content_platform_message_chain(), is_final=final)

    frames = client.stream_frames()
    from langbot.pkg.platform.adapters.wecombot.stream_text import format_stream_text

    assert [frame['stream']['content'] for frame in frames] == [format_stream_text(text) for text in snapshots]
    assert [frame['stream']['finish'] for frame in frames] == [False, False, True]
    assert len(client.replies) == 3  # No extra plain-text reply after completion.


@pytest.mark.asyncio
async def test_revised_snapshot_replaces_previous_text():
    client = RecordingClient()
    client.seed_stream()
    await client.push_stream_chunk('msg-1', '<think>test</think>\nanswer')
    await client.push_stream_chunk('msg-1', 'answer', is_final=True)
    assert client.stream_frames()[-1]['stream']['content'] == 'answer'
