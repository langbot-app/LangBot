"""Exercise real SDK response routing with a delayed Host consumer."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.resp import ActionResponse, ChunkStatus

from langbot.pkg.agent.runner import invoker as invoker_module, stream_receipts
from langbot.pkg.agent.runner.errors import RunnerExecutionError
from langbot.pkg.plugin import handler as handler_module
from tests.unit_tests.plugin.test_connector_methods import create_mock_connector, TEST_EXECUTION_CONTEXT


@pytest.fixture
async def transport(monkeypatch):
    clock = SimpleNamespace(now=100.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now)
    for module in (invoker_module, stream_receipts, handler_module):
        monkeypatch.setattr(module, 'time', fake_time)
    sent = asyncio.Queue()

    async def send(raw):
        await sent.put(json.loads(raw))

    connection = SimpleNamespace(send=send, close=AsyncMock())
    handler = handler_module.RuntimeConnectionHandler(connection, AsyncMock(), SimpleNamespace(logger=Mock()))
    connector = create_mock_connector()
    connector.handler = handler
    reader = invoker_module.RunnerInvoker(SimpleNamespace(plugin_connector=connector, logger=Mock()))
    descriptor = SimpleNamespace(id='test', plugin_author='qa', plugin_name='runner', runner_name='default')
    context = {
        'conversation': {'workspace_id': TEST_EXECUTION_CONTEXT.workspace_uuid},
        'runtime': {'deadline_at': 110.0},
    }
    stream = reader.invoke(descriptor, context)

    async def route(request, data=None, *, end=False, index=None):
        response = ActionResponse.success(data or {})
        response.chunk_status = ChunkStatus.END if end else ChunkStatus.CONTINUE
        response.stream_index = index
        await handler._route_response(request['seq_id'], response.model_dump())

    try:
        yield clock, stream, sent, route, handler
    finally:
        await stream.aclose()
        await handler.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('consume_completed_early', [False, True])
async def test_on_time_completion_and_end_survive_consumer_delay(transport, consume_completed_early):
    clock, stream, sent, route, handler = transport
    first = asyncio.create_task(anext(stream))
    request = await asyncio.wait_for(sent.get(), 2)
    await route(request, {'type': 'message.delta', 'data': {'text': 'hello'}})
    assert (await first)['type'] == 'message.delta'
    clock.now = 105
    completed = {'type': 'run.completed', 'data': {}}
    await route(request, completed)
    if consume_completed_early:
        assert await anext(stream) == completed
    await route(request, end=True)
    clock.now = 115
    if not consume_completed_early:
        assert await anext(stream) == completed
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert not handler._runner_receipts
    assert stream_receipts.current_runner_receipts.get() is None


@pytest.mark.asyncio
async def test_late_frame_is_still_execution_timeout(transport):
    clock, stream, sent, route, _ = transport
    first = asyncio.create_task(anext(stream))
    request = await asyncio.wait_for(sent.get(), 2)
    await route(request, {'type': 'message.delta'})
    await first
    clock.now = 111
    await route(request, {'type': 'run.completed'})
    await route(request, end=True)
    with pytest.raises(RunnerExecutionError) as exc:
        await anext(stream)
    assert exc.value.error_code == 'runner.timeout'


@pytest.mark.asyncio
async def test_receipts_do_not_bypass_sdk_stream_order_validation(transport):
    _, stream, sent, route, _ = transport
    first = asyncio.create_task(anext(stream))
    request = await asyncio.wait_for(sent.get(), 2)
    await route(request, {'type': 'run.completed'}, index=2)
    with pytest.raises(RunnerExecutionError, match='Out-of-order'):
        await first


@pytest.mark.asyncio
@pytest.mark.parametrize('late_end', [False, True])
async def test_completion_does_not_excuse_missing_or_late_end(transport, late_end):
    clock, stream, sent, route, _ = transport
    first = asyncio.create_task(anext(stream))
    request = await asyncio.wait_for(sent.get(), 2)
    await route(request, {'type': 'run.completed'})
    await first
    clock.now = 111
    if late_end:
        await route(request, end=True)
    with pytest.raises(RunnerExecutionError) as exc:
        await anext(stream)
    assert exc.value.error_code == 'runner.timeout'


@pytest.mark.asyncio
async def test_ingress_before_deadline_survives_slow_envelope_validation(transport):
    clock, stream, sent, route, handler = transport
    first = asyncio.create_task(anext(stream))
    request = await asyncio.wait_for(sent.get(), 2)
    await route(request, {'type': 'message.delta'})
    await first
    validate = handler._validate_message_model
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_validation(*args, **kwargs):
        entered.set()
        await release.wait()
        return await validate(*args, **kwargs)

    handler._validate_message_model = slow_validation
    clock.now = 105
    delivery = asyncio.create_task(route(request, {'type': 'run.completed'}))
    await entered.wait()
    clock.now = 111
    consumer = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    release.set()
    await delivery
    assert (await consumer)['type'] == 'run.completed'


def test_receipt_deadline_is_monotonic_and_supports_interaction_extensions(monkeypatch):
    clock = SimpleNamespace(wall=100.0, monotonic=100.0)
    monkeypatch.setattr(
        stream_receipts, 'time', SimpleNamespace(time=lambda: clock.wall, monotonic=lambda: clock.monotonic)
    )
    context = {'runtime': {'deadline_at': 110}}
    receipts = stream_receipts.RunnerStreamReceipts(context)
    clock.wall, clock.monotonic = 200, 105
    assert receipts.remaining() == 5
    context['runtime']['deadline_at'] += 20
    assert receipts.remaining() == 25


@pytest.mark.asyncio
async def test_concurrent_runs_keep_receipts_and_cleanup_separate(transport):
    clock, first_stream, sent, route, handler = transport
    connector = create_mock_connector()
    connector.handler = handler
    reader = invoker_module.RunnerInvoker(SimpleNamespace(plugin_connector=connector, logger=Mock()))
    second_stream = reader.invoke(
        SimpleNamespace(id='second', plugin_author='qa', plugin_name='runner', runner_name='default'),
        {'conversation': {'workspace_id': TEST_EXECUTION_CONTEXT.workspace_uuid}, 'runtime': {'deadline_at': 110}},
    )
    try:
        first = asyncio.create_task(anext(first_stream))
        first_request = await asyncio.wait_for(sent.get(), 2)
        second = asyncio.create_task(anext(second_stream))
        second_request = await asyncio.wait_for(sent.get(), 2)
        await route(first_request, {'type': 'message.delta'})
        await route(second_request, {'type': 'message.delta'})
        await asyncio.gather(first, second)
        clock.now = 105
        await route(second_request, {'type': 'run.completed'})
        await route(second_request, end=True)
        clock.now = 111
        await route(first_request, {'type': 'run.completed'})
        await route(first_request, end=True)
        with pytest.raises(RunnerExecutionError) as exc:
            await anext(first_stream)
        assert exc.value.error_code == 'runner.timeout'
        assert second_request['seq_id'] in handler._runner_receipts
        assert (await anext(second_stream))['type'] == 'run.completed'
        with pytest.raises(StopAsyncIteration):
            await anext(second_stream)
        assert not handler._runner_receipts
    finally:
        await second_stream.aclose()
