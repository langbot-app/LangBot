"""Regression tests for the Coze stream tail-flush in CozeAPIRunner._chat_messages_chunk.

Self-hosted Coze does not emit a terminating ``done`` event, so ``is_final`` can stay
``False`` for the whole stream. The runner only flushes on a ``message_idx % 8 == 0``
boundary, so a stream that ends between boundaries -- or exactly on a boundary -- used
to lose its tail (or, on boundary endings, its terminal signal). These tests drive the
real runner and assert that a complete, terminal snapshot is always delivered on normal
completion and that errors are never reported as success.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from langbot.pkg.provider.runners.cozeapi import CozeAPIRunner


def _make_runner() -> CozeAPIRunner:
    """Build a runner wired to a mock Coze client (no network/API key needed)."""
    mock_app = MagicMock()
    pipeline_config = {
        'ai': {
            'coze-api': {
                'api-key': 'test-key',
                'bot-id': 'bot-1',
                'timeout': 30,
                'auto_save_history': True,
                'api-base': 'https://api.coze.cn',
            }
        },
        'output': {'misc': {'remove-think': False}},
    }
    runner = CozeAPIRunner(mock_app, pipeline_config)
    runner.coze = MagicMock()
    return runner


def _make_query():
    query = MagicMock()
    query.launcher_type.value = 'person'
    query.launcher_id = 'user-1'
    query.session.using_conversation.uuid = 'conversation-1'
    query.user_message.content = 'hello'
    return query


def _delta(content: str) -> dict:
    return {'event': 'conversation.message.delta', 'data': {'content': content}}


def _done() -> dict:
    return {'event': 'done', 'data': {'conversation_id': 'conversation-1'}}


def _error(message: str = 'network down') -> dict:
    return {'event': 'error', 'data': {'message': message}}


def _self_hosted_end() -> dict:
    """Self-hosted Coze finishes on this event, which the runner does not treat as final."""
    return {'event': 'conversation.chat.completed', 'data': {}}


def _set_stream(runner: CozeAPIRunner, chunks: list[dict]) -> None:
    async def chat_messages(**kwargs):
        del kwargs
        for chunk in chunks:
            yield chunk

    runner.coze.chat_messages = chat_messages


async def _collect(runner: CozeAPIRunner, query) -> list:
    return [chunk async for chunk in runner._chat_messages_chunk(query)]


@pytest.mark.parametrize('length', list(range(1, 41)))
async def test_terminal_snapshot_for_every_length_without_done(length: int) -> None:
    """Every stream length with no 'done' must end on a complete, terminal snapshot."""
    runner = _make_runner()
    deltas = [chr(ord('a') + i % 26) for i in range(length)]
    _set_stream(runner, [_delta(d) for d in deltas])

    chunks = await _collect(runner, _make_query())

    assert chunks, 'runner must emit at least one chunk'
    assert chunks[-1].content == ''.join(deltas), 'full response must not be lost'
    assert chunks[-1].is_final is True, 'terminal signal must always be delivered'


@pytest.mark.parametrize('length', [7, 15, 23, 31, 39])
async def test_boundary_ending_is_finalised_once(length: int) -> None:
    """Streams ending exactly on a flush boundary must still get a terminal signal."""
    runner = _make_runner()
    deltas = ['x'] * length
    _set_stream(runner, [_delta(d) for d in deltas])

    chunks = await _collect(runner, _make_query())

    final_chunks = [chunk for chunk in chunks if chunk.is_final]
    assert len(final_chunks) == 1, 'must deliver exactly one terminal snapshot'
    assert final_chunks[0].content == ''.join(deltas), 'terminal snapshot must be complete'


@pytest.mark.parametrize('done_index', list(range(0, 20)) + [None])
async def test_terminal_snapshot_with_done_at_every_position(done_index: int | None) -> None:
    """When Coze does emit 'done', the runner still ends on a complete terminal snapshot."""
    length = 20
    runner = _make_runner()
    # Once 'done' arrives the runner keeps re-emitting a full snapshot per delta
    # (is_final is sticky). That is pre-existing behaviour and out of scope here;
    # these cases only pin that the stream still ends on a complete terminal snapshot.
    stream: list[dict] = []
    for i in range(length):
        if done_index is not None and i == done_index:
            stream.append(_done())
        stream.append(_delta('z'))
    _set_stream(runner, stream)

    chunks = await _collect(runner, _make_query())

    assert chunks[-1].content == 'z' * length
    assert chunks[-1].is_final is True


async def test_self_hosted_end_event_still_yields_terminal_snapshot() -> None:
    """Self-hosted Coze ends on 'conversation.chat.completed' rather than 'done'.

    The runner does not match that event as terminal, so the tail flush is the only
    thing that turns the last chunk into a terminal snapshot.
    """
    runner = _make_runner()
    _set_stream(runner, [_delta('a'), _delta('b'), _delta('c'), _self_hosted_end()])

    chunks = await _collect(runner, _make_query())

    assert chunks[-1].content == 'abc', 'content must survive the unrecognised end event'
    assert chunks[-1].is_final is True, 'the end event must still finalise the stream'


async def test_error_event_is_not_terminal_success() -> None:
    """An 'error' event must surface as an error, never as a normal final snapshot."""
    runner = _make_runner()
    deltas = ['a', 'b', 'c']
    _set_stream(runner, [_delta(d) for d in deltas] + [_error('network down')])

    chunks = await _collect(runner, _make_query())

    # MessageChunk carries no finish_reason field, so the error is only observable
    # through its content plus the absence of the successful terminal signal.
    assert 'network down' in chunks[-1].content, 'the error must reach the user'
    assert not any(chunk.is_final for chunk in chunks), 'an error must not be finalised as success'


async def test_stream_exception_is_not_finalised_as_success() -> None:
    """A mid-stream failure must not be completed by the tail flush."""
    runner = _make_runner()

    async def broken_stream(**kwargs):
        del kwargs
        yield _delta('a')
        raise RuntimeError('stream broke')

    runner.coze.chat_messages = broken_stream

    chunks = await _collect(runner, _make_query())

    assert 'stream broke' in chunks[-1].content, 'the failure must reach the user'
    assert not any(chunk.is_final for chunk in chunks), 'a broken stream must not look complete'
