"""Streaming lifetimes: debug cancellation versus durable Assistant execution."""

from __future__ import annotations

import asyncio
import contextvars
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk

from langbot.pkg.api.application.service_operations import TurnInput, _assistant_service
from langbot.pkg.api.application.workspace_streams import AgentDebugInput, agent_debug, assistant_turn
from langbot.pkg.api.http.service.assistant import AssistantError
from tests.unit_tests.api.test_management_assistant import context

pytest_plugins = ['tests.unit_tests.api.test_management_assistant']


def scoped_app(debug):
    active = contextvars.ContextVar('debug_stream_scope', default=None)

    @asynccontextmanager
    async def tenant_scope(workspace_uuid):
        token = active.set((workspace_uuid, asyncio.current_task()))
        try:
            yield
        finally:
            active.reset(token)

    return SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_scope=tenant_scope),
        agent_service=SimpleNamespace(debug_agent=debug),
    ), active


@pytest.mark.asyncio
async def test_debug_stream_delivers_callbacks_before_completion_and_propagates_failure():
    release = asyncio.Event()

    async def debug(ctx, agent_uuid, payload, on_result):
        assert active.get() == (ctx.workspace_uuid, asyncio.current_task())
        await on_result({'text': payload['text']})
        await release.wait()
        return {'agent_uuid': agent_uuid, 'status': 'completed'}

    ap, active = scoped_app(debug)
    stream = await agent_debug(ap, context(), AgentDebugInput(agent_uuid='agent', payload={'text': 'partial'}))
    assert await anext(stream) == {'kind': 'result', 'data': {'text': 'partial'}}
    assert active.get() is None
    release.set()
    assert await anext(stream) == {'kind': 'completed', 'data': {'agent_uuid': 'agent', 'status': 'completed'}}
    await stream.aclose()

    async def failed(*args, **kwargs):
        raise ValueError('invalid debug input')

    ap.agent_service.debug_agent = failed
    failed_stream = await agent_debug(ap, context(), AgentDebugInput(agent_uuid='agent', payload={}))
    with pytest.raises(ValueError, match='invalid debug input'):
        await anext(failed_stream)


@pytest.mark.asyncio
async def test_debug_stream_applies_backpressure_and_close_cancels_producer():
    completed_callbacks = 0
    saturated = asyncio.Event()
    cancelled = asyncio.Event()

    async def debug(ctx, agent_uuid, payload, on_result):
        nonlocal completed_callbacks
        try:
            for index in range(100):
                if index == 33:
                    saturated.set()
                await on_result({'index': index})
                completed_callbacks += 1
        finally:
            cancelled.set()

    ap, _ = scoped_app(debug)
    stream = await agent_debug(ap, context(), AgentDebugInput(agent_uuid='agent', payload={}))
    assert (await anext(stream))['data']['index'] == 0
    await asyncio.wait_for(saturated.wait(), 1)
    assert completed_callbacks == 33
    assert not cancelled.is_set()
    await stream.aclose()
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_assistant_stream_disconnect_preserves_run_and_bounded_queue(assistant):
    _, ap, provider = assistant
    service = _assistant_service(ap)
    release = asyncio.Event()

    async def model_stream(**kwargs):
        yield MessageChunk(role='assistant', content='first')
        await release.wait()
        for _ in range(100):
            yield MessageChunk(role='assistant', content='x')
        yield MessageChunk(role='assistant', content=' done', is_final=True)

    provider.invoke_llm_stream = model_stream
    ctx = context()
    conversation_id = (await service.create(ctx))['uuid']
    stream = await assistant_turn(ap, ctx, TurnInput(conversation_id=conversation_id, revision=0, text='Hi'))
    try:
        while (await asyncio.wait_for(anext(stream), 2))['kind'] != 'text':
            pass
        task = service._runs[conversation_id]['task']
        queue = service._runs[conversation_id]['queue']
        assert queue.maxsize == 32
        await stream.aclose()
        assert not task.done()
        assert _assistant_service(ap) is service
        assert (await service.progress(ctx, conversation_id))['progress']['text'] == 'first'
        release.set()
        await asyncio.wait_for(task, 3)
        completed = await service.get(ctx, conversation_id)
        assert completed['status'] == 'ready'
        assert completed['messages'][-1]['content'] == 'first' + 'x' * 100 + ' done'
        assert queue.qsize() == 32
        frames = [queue.get_nowait() for _ in range(queue.qsize())]
        assert frames[-1]['kind'] == 'completed'
        with pytest.raises(AssistantError, match='conversation_not_found'):
            await assistant_turn(
                ap, context(account='other'), TurnInput(conversation_id=conversation_id, revision=1, text='steal')
            )
        with pytest.raises(ValueError, match='Provide text or an approval decision'):
            await assistant_turn(
                ap, ctx, TurnInput(conversation_id=conversation_id, revision=1, text='both', approved=True)
            )
    finally:
        release.set()
        await stream.aclose()
        for run in list(service._runs.values()):
            await asyncio.wait_for(run['task'], 3)


@pytest.mark.asyncio
async def test_debug_provider_cancellation_wakes_subscriber_without_timeout():
    finished = asyncio.Event()

    async def cancelled(*args, **kwargs):
        try:
            raise asyncio.CancelledError()
        finally:
            finished.set()

    ap, active = scoped_app(cancelled)
    stream = await agent_debug(ap, context(), AgentDebugInput(agent_uuid='agent', payload={}))
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(anext(stream), 0.5)
    assert finished.is_set()
    assert active.get() is None
    await stream.aclose()
