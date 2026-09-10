"""Explicit streaming delivery across SDK, Host lifecycle, and adapter boundaries."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langbot_plugin.api.entities.builtin.platform import events, entities, message
from langbot_plugin.api.entities.builtin.runner.context_access import ContextAPICapabilities
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.api.proxies.runner.common import PermissionDeniedError
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from langbot.pkg.agent.runner.reply_stream import ReplyStreamRequest, ReplyStreamSession


def make_session(*, native=True, source=True, mock=False):
    event = SimpleNamespace(
        delivery=SimpleNamespace(
            surface='webui' if mock else 'platform',
            platform_capabilities={'debug_mock': mock},
            reply_target={'target_type': 'person', 'target_id': 'user-1'},
        )
    )
    incoming = (
        events.MessageReceivedEvent(
            message_id='source-1',
            sender=entities.User(id='user-1'),
            chat_id='user-1',
            chat_type=entities.ChatType.PRIVATE,
            message_chain=message.MessageChain([message.Plain(text='hello')]),
            source_platform_object=object(),
        )
        if source
        else None
    )
    adapter = SimpleNamespace(
        is_stream_output_supported=AsyncMock(return_value=native),
        create_message_card=AsyncMock(return_value=True),
        reply_message_chunk=AsyncMock(),
        send_message=AsyncMock(),
        reply_message=AsyncMock(),
    )
    return ReplyStreamSession(event, adapter, incoming), adapter, incoming


def request(key, operation='update', text='hello'):
    return ReplyStreamRequest(stream_id=key, operation=operation, text=text)


def proxy_for(session, *, allowed=True, advertised=True):
    if not hasattr(RunnerAPIProxy, 'reply_stream'):
        pytest.skip('SDK does not provide the optional streaming reply API')
    context = SimpleNamespace(
        run_id='run-1',
        runtime=SimpleNamespace(deadline_at=None),
        context=SimpleNamespace(available_apis=ContextAPICapabilities(reply_stream=advertised)),
        resources=SimpleNamespace(
            models=[],
            knowledge_bases=[],
            tools=[SimpleNamespace(tool_name='event_reply', operations=['call'])] if allowed else [],
        ),
    )

    async def action(action, data, timeout):
        assert action == PluginToRuntimeAction.REPLY_STREAM
        assert data['run_id'] == 'run-1'
        return {
            'result': await session.apply(
                ReplyStreamRequest.model_validate({k: v for k, v in data.items() if k != 'run_id'})
            )
        }

    transport = SimpleNamespace(call_action=AsyncMock(side_effect=action))
    return RunnerAPIProxy(context, transport), transport


@pytest.mark.parametrize(
    'native,source,mock',
    [
        (True, True, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
async def test_sdk_stream_reuses_adapter_or_sends_one_final_message(native, source, mock):
    session, adapter, incoming = make_session(native=native, source=source, mock=mock)
    api, transport = proxy_for(session)
    async with api.reply_stream() as stream:
        await stream.update('hello')
        await stream.update('hello world')
        adapter.send_message.assert_not_awaited()
        adapter.reply_message.assert_not_awaited()
    assert stream.result['status'] == 'completed'
    assert stream.result['text'] == 'hello world'
    assert transport.call_action.await_count == 3
    if mock:
        adapter.create_message_card.assert_not_awaited()
        adapter.reply_message_chunk.assert_not_awaited()
        adapter.send_message.assert_not_awaited()
        assert stream.result['mock'] is True
    elif native and source:
        adapter.create_message_card.assert_awaited_once()
        delivered_source = adapter.create_message_card.await_args.args[1]
        assert delivered_source.source_platform_object is incoming.source_platform_object
        chunks = adapter.reply_message_chunk.await_args_list
        assert [c.kwargs['bot_message'].all_content for c in chunks] == ['hello', 'hello world', 'hello world']
        assert [c.kwargs['is_final'] for c in chunks] == [False, False, True]
        assert chunks[-1].kwargs['bot_message'].tool_calls is None
    else:
        adapter.reply_message_chunk.assert_not_awaited()
        if source:
            adapter.reply_message.assert_awaited_once()
            assert adapter.reply_message.await_args.kwargs['message'][0].text == 'hello world'
        else:
            adapter.send_message.assert_awaited_once()
            assert adapter.send_message.await_args.args[2][0].text == 'hello world'
    await session.close()


@pytest.mark.parametrize('native', [True, False])
@pytest.mark.parametrize('error', [RuntimeError, asyncio.CancelledError])
async def test_exception_finalizes_visible_card_without_sending_buffered_partial(native, error):
    session, adapter, _ = make_session(native=native)
    api, _ = proxy_for(session)
    with pytest.raises(error):
        async with api.reply_stream() as stream:
            await stream.update('partial')
            raise error()
    if native:
        assert adapter.reply_message_chunk.await_args.kwargs['is_final'] is True
    adapter.reply_message.assert_not_awaited()
    adapter.send_message.assert_not_awaited()
    count = adapter.reply_message_chunk.await_count
    await session.close()
    assert adapter.reply_message_chunk.await_count == count


@pytest.mark.parametrize('allowed,advertised', [(False, True), (True, False)])
async def test_missing_permission_or_old_host_fails_before_delivery(allowed, advertised):
    session, _, _ = make_session()
    api, transport = proxy_for(session, allowed=allowed, advertised=advertised)
    with pytest.raises(PermissionDeniedError):
        async with api.reply_stream():
            pytest.fail('Not authorized')
    transport.call_action.assert_not_awaited()


async def test_empty_stream_and_duplicate_finish_do_not_send_twice():
    session, adapter, _ = make_session(native=False)
    empty = uuid4()
    await session.apply(request(empty, 'finish', ''))
    adapter.reply_message.assert_not_awaited()
    key = uuid4()
    await session.apply(request(key))
    first = await session.apply(request(key, 'finish'))
    assert await session.apply(request(key, 'finish')) == first
    adapter.reply_message.assert_awaited_once()
    with pytest.raises(ValueError, match='closed'):
        await session.apply(request(key))
    await session.close()
    with pytest.raises(ValueError, match='ended'):
        await session.apply(request(uuid4()))


async def test_host_cleanup_closes_stream_when_plugin_disappears():
    session, adapter, _ = make_session()
    await session.apply(request(uuid4()))
    await session.close()
    assert adapter.reply_message_chunk.await_args.kwargs['is_final'] is True


async def test_uncertain_final_send_is_not_retried_by_finish_or_cleanup():
    session, adapter, _ = make_session(native=False)
    adapter.reply_message.side_effect = TimeoutError('Response lost')
    key = uuid4()
    with pytest.raises(TimeoutError):
        await session.apply(request(key, 'finish'))
    with pytest.raises(ValueError, match='closed'):
        await session.apply(request(key, 'finish'))
    await session.close()
    adapter.reply_message.assert_awaited_once()


async def test_failed_update_closes_existing_card_during_run_cleanup():
    session, adapter, _ = make_session()
    adapter.reply_message_chunk.side_effect = [RuntimeError('update failed'), None]
    with pytest.raises(RuntimeError):
        await session.apply(request(uuid4()))
    await session.close()
    assert adapter.reply_message_chunk.await_args.kwargs['is_final'] is True


async def test_streams_are_isolated_by_run_and_bounded():
    first, a, _ = make_session(native=False)
    second, b, _ = make_session(native=False)
    key = uuid4()
    await first.apply(request(key, 'update', 'first'))
    await second.apply(request(key, 'finish', 'second'))
    assert b.reply_message.await_args.kwargs['message'][0].text == 'second'
    a.reply_message.assert_not_awaited()
    for _ in range(15):
        await first.apply(request(uuid4(), 'finish', ''))
    with pytest.raises(ValueError, match='at most'):
        await first.apply(request(uuid4()))
    await first.close()
    a.reply_message.assert_not_awaited()


async def test_event_processor_uses_shared_sdk_api_and_emits_one_trace_for_the_stream():
    from unittest.mock import Mock
    from langbot_plugin.api.definition.components.runner import Runner, RunnerContext

    session, adapter, incoming = make_session()
    api, _ = proxy_for(session)
    processor = Runner()
    processor.get_run_api = Mock(return_value=api)

    @processor.handler(events.MessageReceivedEvent)
    async def handle(ctx):
        async with ctx.reply_stream() as stream:
            await stream.update('one')
            await stream.update('one two')

    context = RunnerContext.model_validate(
        {
            'run_id': 'run-1',
            'trigger': {'type': incoming.type},
            'event': {
                'event_id': 'one',
                'event_type': incoming.type,
                'source': 'test',
                'data': incoming.model_dump(mode='json', exclude={'source_platform_object', 'legacy_event'}),
            },
            'input': {},
            'delivery': {'surface': 'test'},
            'resources': {},
            'runtime': {},
        }
    )
    results = [result async for result in processor.invoke(context)]
    assert [r.type for r in results] == ['tool.call.started', 'tool.call.completed', 'run.completed']
    assert results[1].data['result']['text'] == 'one two'
    assert adapter.reply_message_chunk.await_count == 3
    await session.close()


async def test_shared_adapter_uses_host_ids_to_isolate_identical_plugin_stream_ids():
    first, adapter, _ = make_session()
    second, _, _ = make_session()
    second.adapter = adapter
    key = uuid4()
    await first.apply(request(key, text='first'))
    await second.apply(request(key, text='second'))
    ids = [c.args[0] for c in adapter.create_message_card.await_args_list]
    assert len(set(ids)) == 2
    assert str(key) not in ids
    await first.close()
    await second.close()


async def test_run_cleanup_cancels_inflight_update_and_finalizes_card():
    session, adapter, _ = make_session()
    started = asyncio.Event()

    async def update(**kwargs):
        if not kwargs['is_final']:
            started.set()
            await asyncio.Event().wait()

    adapter.reply_message_chunk.side_effect = update
    task = asyncio.create_task(session.apply(request(uuid4())))
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.wait_for(session.close(), 1)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert adapter.reply_message_chunk.await_args.kwargs['is_final'] is True
