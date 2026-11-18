"""Input counting is independent of generation reasoning policy."""

import asyncio
import threading
from unittest.mock import Mock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.provider.modelmgr import errors
from langbot.pkg.provider.modelmgr.requesters import litellmchat
from tests.unit_tests.provider.test_reasoning_control import _requester, _runtime_model


@pytest.mark.asyncio
@pytest.mark.parametrize('abilities', [[], ['reasoning']])
async def test_count_ignores_unsupported_reasoning_without_reading_credentials(monkeypatch, abilities):
    request = _requester('anthropic')
    model = _runtime_model(request, name='claude-sonnet-5', abilities=abilities)
    model.reasoning_config_override = {'level': 'minimal'}
    model.provider.token_mgr.get_token = Mock(side_effect=AssertionError('Counting does not need credentials'))
    counter = Mock(return_value=13)
    monkeypatch.setattr(litellmchat.litellm, 'token_counter', counter)

    assert await request.count_tokens(model, [Message(role='user', content='hello')]) == 13
    assert counter.call_args.kwargs == {
        'model': 'anthropic/claude-sonnet-5',
        'messages': [{'role': 'user', 'content': 'hello'}],
    }
    with pytest.raises(errors.RequesterError):
        request._build_reasoning_args(model)


@pytest.mark.asyncio
async def test_count_preserves_input_overrides(monkeypatch):
    request = _requester('openai')
    model = _runtime_model(request, name='gpt-4o')
    tools = [{'type': 'function', 'function': {'name': 'search', 'parameters': {'type': 'object'}}}]
    model.model_entity.extra_args = {'tools': tools, 'tool_choice': 'auto', 'temperature': 0.2}
    counter = Mock(return_value=37)
    monkeypatch.setattr(litellmchat.litellm, 'token_counter', counter)

    assert await request.count_tokens(model, [], extra_args={'tool_choice': 'none'}) == 37
    assert counter.call_args.kwargs == {'model': 'openai/gpt-4o', 'messages': [], 'tools': tools, 'tool_choice': 'none'}


@pytest.mark.asyncio
async def test_stalled_counter_is_bounded_and_does_not_queue_more_threads(monkeypatch):
    request = _requester('openai')
    request.TOKEN_COUNT_TIMEOUT = 0.02
    model = _runtime_model(request, name='gpt-4o')
    release = threading.Event()
    calls = []

    def stalled(**kwargs):
        calls.append(kwargs)
        release.wait(2)
        return 8

    monkeypatch.setattr(litellmchat.litellm, 'token_counter', stalled)
    try:
        with pytest.raises(errors.RequesterError, match='time limit'):
            await request.count_tokens(model, [])
        with pytest.raises(errors.RequesterError, match='still busy'):
            await request.count_tokens(model, [])
        assert len(calls) == 1
    finally:
        release.set()
        await request._stalled_count_task
    assert await request.count_tokens(model, []) == 8


@pytest.mark.asyncio
async def test_cancelled_count_does_not_release_busy_worker(monkeypatch):
    request = _requester('openai')
    model = _runtime_model(request, name='gpt-4o')
    started = asyncio.Event()
    release = asyncio.Event()

    async def worker(*args, **kwargs):
        started.set()
        await release.wait()
        return 8

    monkeypatch.setattr(litellmchat.asyncio, 'to_thread', worker)
    caller = asyncio.create_task(request.count_tokens(model, []))
    await started.wait()
    caller.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await caller
        with pytest.raises(errors.RequesterError, match='still busy'):
            await request.count_tokens(model, [])
    finally:
        release.set()
        await request._stalled_count_task


@pytest.mark.asyncio
async def test_concurrent_counts_on_one_requester_all_succeed(monkeypatch):
    request = _requester('openai')
    model = _runtime_model(request, name='gpt-4o')
    inside = 0
    peak = 0
    lock = threading.Lock()

    def slow(**kwargs):
        nonlocal inside, peak
        with lock:
            inside += 1
            peak = max(peak, inside)
        threading.Event().wait(0.05)
        with lock:
            inside -= 1
        return 21

    monkeypatch.setattr(litellmchat.litellm, 'token_counter', slow)

    results = await asyncio.gather(*(request.count_tokens(model, []) for _ in range(8)))

    assert results == [21] * 8
    assert peak > 1
    assert request._stalled_count_task is None
