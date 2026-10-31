"""Regression coverage for installation scopes across async-generator resumes."""

import asyncio
import contextvars
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from langbot.pkg.agent.runner.errors import RunnerExecutionError
from langbot.pkg.agent.runner.invoker import RunnerInvoker
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot.pkg.plugin.connector import PluginRuntimeConnector
from tests.unit_tests.plugin.test_connector_methods import (
    TEST_EXECUTION_CONTEXT,
    TEST_INSTALLATION_BINDING,
    create_mock_connector,
)


def make_stream(*, deadline=True, failure=None, blocked=False):
    handler = object.__new__(RuntimeConnectionHandler)
    handler._outbound_installation_context = contextvars.ContextVar('test_installation', default=None)
    entered = asyncio.Event()
    closed = []
    observed = []

    async def wire_stream(*args, **kwargs):
        try:
            for index in range(3):
                observed.append(handler._outbound_installation_context.get())
                if index == 1:
                    entered.set()
                    if blocked:
                        await asyncio.Event().wait()
                    if failure:
                        raise failure
                yield {'type': 'message.delta', 'sequence': index}
        finally:
            closed.append(handler._outbound_installation_context.get())

    handler.call_action_generator = wire_stream
    connector = create_mock_connector()
    connector.handler = handler
    invoker = RunnerInvoker(SimpleNamespace(plugin_connector=connector, logger=Mock()))
    descriptor = SimpleNamespace(
        id='plugin:qa/runner/default', plugin_author='qa', plugin_name='runner', runner_name='default'
    )
    context = {
        'conversation': {'workspace_id': TEST_EXECUTION_CONTEXT.workspace_uuid},
        'runtime': {'deadline_at': time.time() + 10 if deadline else None},
    }
    return invoker.invoke(descriptor, context), handler, context, entered, closed, observed


@pytest.mark.asyncio
@pytest.mark.parametrize('deadline', [True, False])
async def test_scope_is_reset_before_yield_and_stream_finishes(deadline):
    stream, handler, _, _, closed, observed = make_stream(deadline=deadline)
    frames = []
    async for frame in stream:
        frames.append(frame)
        assert handler._outbound_installation_context.get() is None
        await asyncio.sleep(0)
    assert [frame['sequence'] for frame in frames] == [0, 1, 2]
    assert observed == [TEST_INSTALLATION_BINDING] * 3
    assert closed == [TEST_INSTALLATION_BINDING]


@pytest.mark.asyncio
@pytest.mark.parametrize('deadline', [True, False])
async def test_early_close_releases_wire_stream_in_scope(deadline):
    stream, handler, _, _, closed, _ = make_stream(deadline=deadline)
    await anext(stream)
    await stream.aclose()
    assert closed == [TEST_INSTALLATION_BINDING]
    assert handler._outbound_installation_context.get() is None


@pytest.mark.asyncio
async def test_deadline_expired_between_frames_closes_in_scope():
    stream, handler, context, _, closed, _ = make_stream()
    await anext(stream)
    context['runtime']['deadline_at'] = time.time() - 1
    with pytest.raises(RunnerExecutionError) as exc:
        await anext(stream)
    assert exc.value.error_code == 'runner.timeout'
    assert closed == [TEST_INSTALLATION_BINDING]
    assert handler._outbound_installation_context.get() is None


@pytest.mark.asyncio
async def test_timeout_during_next_frame_keeps_timeout_error():
    stream, handler, context, _, closed, _ = make_stream(blocked=True)
    await anext(stream)
    context['runtime']['deadline_at'] = time.time() + 0.05
    with pytest.raises(RunnerExecutionError) as exc:
        await anext(stream)
    assert exc.value.error_code == 'runner.timeout'
    assert closed == [TEST_INSTALLATION_BINDING]
    assert handler._outbound_installation_context.get() is None


@pytest.mark.asyncio
async def test_cancellation_preserves_cancelled_error_and_cleans_up():
    stream, handler, _, entered, closed, _ = make_stream(blocked=True)
    await anext(stream)
    task = asyncio.create_task(anext(stream))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == [TEST_INSTALLATION_BINDING]
    assert handler._outbound_installation_context.get() is None


@pytest.mark.asyncio
async def test_transport_error_is_not_masked_by_context_reset():
    stream, handler, _, _, closed, _ = make_stream(failure=RuntimeError('wire failed'))
    await anext(stream)
    with pytest.raises(RunnerExecutionError, match='wire failed'):
        await anext(stream)
    assert closed == [TEST_INSTALLATION_BINDING]
    assert handler._outbound_installation_context.get() is None


@pytest.mark.asyncio
async def test_interleaved_installations_share_handler_without_scope_leakage():
    handler = object.__new__(RuntimeConnectionHandler)
    handler._outbound_installation_context = contextvars.ContextVar('shared_installation', default=None)
    other_binding = TEST_INSTALLATION_BINDING.model_copy(
        update={'installation_uuid': '00000000-0000-4000-8000-000000000002'}
    )
    closed = []

    async def wire(binding):
        try:
            for index in range(3):
                assert handler._outbound_installation_context.get() == binding
                await asyncio.sleep(0)
                assert handler._outbound_installation_context.get() == binding
                yield index
        finally:
            assert handler._outbound_installation_context.get() == binding
            closed.append(binding)

    async def consume(binding):
        stream = PluginRuntimeConnector._installation_scoped_stream(handler, binding, wire(binding))
        for index in range(3):
            assert await asyncio.wait_for(anext(stream), 1) == index
            assert handler._outbound_installation_context.get() is None
        # Closing in yet another task must also restore that task's context.
        await asyncio.wait_for(stream.aclose(), 1)

    await asyncio.gather(consume(TEST_INSTALLATION_BINDING), consume(other_binding))
    assert set(closed) == {TEST_INSTALLATION_BINDING, other_binding}
    assert handler._outbound_installation_context.get() is None
