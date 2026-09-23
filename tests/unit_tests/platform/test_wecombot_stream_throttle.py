"""Regression tests for WeCom AI Bot stream frame throttling.

A WeCom stream frame replaces the whole bubble and must carry the complete
snapshot, so forwarding every runner chunk re-uploads the growing answer over
and over on long replies. ``push_stream_chunk`` now spaces intermediate frames
out; these tests lock in that behaviour without touching a socket.

Covered here:

* the first frame of a message always goes out;
* intermediate frames inside the interval are dropped;
* a later frame goes out once the interval has elapsed;
* the final chunk is never throttled, so a reply always terminates;
* dropped frames lose no content, because the runner sends cumulative
  snapshots and the closing frame still carries the whole answer;
* throttle state is tracked per message and released when the stream finishes.
"""

import time

import pytest

import langbot.pkg.core.app  # noqa: F401
from langbot.libs.wecom_ai_bot_api import ws_client
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

    def seed_stream(self, msg_id='msg-1', req_id='req-1', stream_id='stream-1'):
        self._stream_ids[msg_id] = f'{req_id}|{stream_id}'
        self._stream_sessions[msg_id] = {
            'req_id': req_id,
            'stream_id': stream_id,
            'msg_id': msg_id,
            'user_id': 'user-1',
            'chat_id': 'chat-1',
            'chat_type': 'single',
        }

    def stream_frames(self):
        return [body for _cmd, _req, body in self.replies if body.get('msgtype') == 'stream']


@pytest.fixture
def frozen_throttle(monkeypatch):
    """Widen the interval so every intermediate frame falls inside it."""
    monkeypatch.setattr(ws_client, '_STREAM_PUSH_MIN_INTERVAL', 3600.0)


@pytest.mark.asyncio
async def test_first_chunk_of_a_message_is_always_pushed(frozen_throttle):
    client = RecordingClient()
    client.seed_stream()

    await client.push_stream_chunk('msg-1', 'hello', is_final=False)

    assert len(client.stream_frames()) == 1


@pytest.mark.asyncio
async def test_intermediate_chunks_inside_the_interval_are_dropped(frozen_throttle):
    client = RecordingClient()
    client.seed_stream()

    for i in range(1, 31):
        await client.push_stream_chunk('msg-1', 'a' * i, is_final=False)

    assert len(client.stream_frames()) == 1


@pytest.mark.asyncio
async def test_chunk_is_pushed_once_the_interval_has_elapsed(monkeypatch):
    monkeypatch.setattr(ws_client, '_STREAM_PUSH_MIN_INTERVAL', 0.5)
    client = RecordingClient()
    client.seed_stream()

    await client.push_stream_chunk('msg-1', 'a', is_final=False)
    client._stream_last_push_at['msg-1'] = time.monotonic() - 10.0
    await client.push_stream_chunk('msg-1', 'ab', is_final=False)

    frames = client.stream_frames()
    assert len(frames) == 2
    assert frames[-1]['stream']['content'] == 'ab'


@pytest.mark.asyncio
async def test_final_chunk_bypasses_the_throttle(frozen_throttle):
    client = RecordingClient()
    client.seed_stream()

    await client.push_stream_chunk('msg-1', 'a', is_final=False)
    await client.push_stream_chunk('msg-1', 'ab', is_final=True)

    frames = client.stream_frames()
    assert len(frames) == 2
    assert frames[-1]['stream']['content'] == 'ab'
    assert frames[-1]['stream']['finish'] is True


@pytest.mark.asyncio
async def test_dropped_frames_do_not_lose_content(frozen_throttle):
    client = RecordingClient()
    client.seed_stream()

    for i in range(1, 31):
        await client.push_stream_chunk('msg-1', 'a' * i, is_final=False)
    await client.push_stream_chunk('msg-1', 'a' * 30, is_final=True)

    frames = client.stream_frames()
    assert len(frames) == 2
    assert frames[-1]['stream']['content'] == 'a' * 30


@pytest.mark.asyncio
async def test_throttle_is_tracked_per_message(frozen_throttle):
    client = RecordingClient()
    client.seed_stream('msg-1', req_id='req-1', stream_id='stream-1')
    client.seed_stream('msg-2', req_id='req-2', stream_id='stream-2')

    await client.push_stream_chunk('msg-1', 'a', is_final=False)
    await client.push_stream_chunk('msg-2', 'b', is_final=False)

    frames = client.stream_frames()
    assert len(frames) == 2
    assert 'msg-1' in client._stream_last_push_at
    assert 'msg-2' in client._stream_last_push_at


@pytest.mark.asyncio
async def test_throttle_state_is_released_when_the_stream_finishes(frozen_throttle):
    client = RecordingClient()
    client.seed_stream()

    await client.push_stream_chunk('msg-1', 'a', is_final=False)
    await client.push_stream_chunk('msg-1', 'ab', is_final=True)

    assert 'msg-1' not in client._stream_last_push_at
