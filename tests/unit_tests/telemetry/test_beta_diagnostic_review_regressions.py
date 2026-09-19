"""Independent-review regressions through real ownership and lifecycle boundaries."""

import asyncio
import importlib.metadata
import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.provider.modelmgr.requester import RuntimeProvider
from langbot.pkg.telemetry import diagnostics as d


def make_ap(identity='instance-test', disabled=False):
    ap = NS(instance_config=NS(data={'space': {'url': 'https://example.invalid', 'disable_telemetry': disabled}}))
    ap.diagnostics = d.DiagnosticsManager(ap, version='4.11.0b2', instance_id=identity)
    return ap


def context(identity='instance-test'):
    return ExecutionContext(instance_uuid=identity, workspace_uuid=str(uuid4()), placement_generation=1)


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [True, False])
async def test_real_runtime_provider_cannot_use_other_app_manager(disabled):
    a, b = make_ap('instance-A'), make_ap('instance-B', disabled)
    ca, cb = context('instance-A'), context('instance-B')
    requester = NS(ap=b, invoke_llm=AsyncMock(return_value='business result'))
    provider = RuntimeProvider(cb, NS(workspace_uuid=cb.workspace_uuid), None, requester)
    model = NS(execution_context=cb, provider=provider)
    parent = d.Span(a.diagnostics, 'api', 'review.parent', {'workspace_uuid': ca.workspace_uuid})
    with parent.activate():
        assert await provider.invoke_llm(None, model, [], execution_context=cb) == 'business result'
    assert not [e for e in a.diagnostics.pending if e['operation'] == 'model.invoke_llm']
    assert len(b.diagnostics.pending) == (0 if disabled else 2)
    for event in b.diagnostics.pending:
        assert event['instance_id'] == 'instance-B'
        assert event['workspace_uuid'] == cb.workspace_uuid
        assert event['trace_id'] != parent.fields['trace_id']


@pytest.mark.asyncio
@pytest.mark.parametrize('shape', ['app', 'ap', 'logger', 'requester', 'adapter', 'direct', 'absent'])
async def test_explicit_disabled_owner_blocks_parent_even_in_ownerless_children(shape):
    a, b = make_ap('instance-A'), make_ap('instance-B', True)
    shapes = {
        'app': b,
        'ap': NS(ap=b),
        'logger': NS(logger=NS(ap=b)),
        'requester': NS(requester=NS(ap=b)),
        'adapter': NS(adapter=NS(logger=NS(ap=b))),
        'direct': NS(diagnostics=b.diagnostics),
        'absent': NS(ap=None),
    }

    @d.observe('api', 'review.child')
    async def child(data):
        d.event(data, 'api', 'review.point', 'succeeded')
        return 42

    @d.observe('api', 'review.owner')
    async def call(owner):
        return await child({})

    @d.observe('run', 'review.stream')
    async def stream(owner):
        yield await child({})

    parent = d.Span(a.diagnostics, 'api', 'review.parent', {})
    with parent.activate():
        assert await call(shapes[shape]) == 42
        assert [x async for x in stream(shapes[shape])] == [42]
        d.event(shapes[shape], 'api', 'review.point', 'succeeded')
    assert len(a.diagnostics.pending) == 1
    assert not b.diagnostics.pending


@pytest.mark.asyncio
async def test_context_cannot_select_other_instance_or_owned_workspace():
    ap = make_ap()
    ca, cb = context(), context('instance-other')

    @d.observe('api', 'review.context')
    async def call(owner, execution_context):
        return 42

    owner = NS(ap=ap, execution_context=ca)
    with d.Span(ap.diagnostics, 'api', 'review.parent', {'workspace_uuid': ca.workspace_uuid}).activate():
        assert await call(owner, cb) == 42
        assert await call(owner, context()) == 42
    assert not [e for e in ap.diagnostics.pending if e['operation'] == 'review.context']
    # A misplaced manager attachment is not an authoritative manager for B.
    other = make_ap('instance-other')
    other.diagnostics = ap.diagnostics
    assert await call(NS(ap=other), cb) == 42
    assert not [e for e in ap.diagnostics.pending if e['operation'] == 'review.context']


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
@pytest.mark.parametrize('action', ['aclose', 'athrow_exit', 'athrow_value', 'athrow_cancel'])
async def test_cleanup_exception_identity_matches_native(disabled, action):
    ap = make_ap(disabled=disabled)
    cleanup_error = ValueError('CANARY cleanup')

    async def original(owner):
        try:
            yield 1
        finally:
            raise cleanup_error

    for fn in (original, d.observe('run', 'review.cleanup')(original)):
        gen = fn(ap)
        assert isinstance(gen, AsyncGenerator)
        assert await anext(gen) == 1
        with pytest.raises(ValueError) as caught:
            if action == 'aclose':
                await gen.aclose()
            else:
                error = {
                    'athrow_exit': GeneratorExit(),
                    'athrow_value': KeyError('business'),
                    'athrow_cancel': asyncio.CancelledError('cancel'),
                }[action]
                await gen.athrow(error)
        assert caught.value is cleanup_error
        assert d.current_span() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
async def test_athrow_generator_exit_can_yield_and_close_remains_native(disabled):
    ap = make_ap(disabled=disabled)

    async def original(owner):
        try:
            yield 1
        except GeneratorExit:
            yield 2
        yield 3

    for fn in (original, d.observe('run', 'review.exit')(original)):
        gen = fn(ap)
        assert await anext(gen) == 1
        assert await gen.athrow(GeneratorExit()) == 2
        assert await anext(gen) == 3
        await gen.aclose()
        gen = fn(ap)
        assert await anext(gen) == 1
        with pytest.raises(RuntimeError, match='ignored GeneratorExit'):
            await gen.aclose()
        # The native generator is still suspended after the refused close.
        assert await anext(gen) == 3
        with pytest.raises(StopAsyncIteration):
            await anext(gen)
        await gen.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
async def test_generator_send_throw_cancellation_and_primary_exception(disabled):
    ap = make_ap(disabled=disabled)
    entered = asyncio.Event()
    primary = ValueError('CANARY business')

    async def original(owner):
        value = yield 1
        try:
            yield value
        except KeyError:
            yield 3
        entered.set()
        await asyncio.Event().wait()

    for fn in (original, d.observe('run', 'review.protocol')(original)):
        gen = fn(ap)
        assert await anext(gen) == 1
        assert await gen.asend(7) == 7
        assert await gen.athrow(KeyError('throw')) == 3
        entered.clear()
        task = asyncio.create_task(anext(gen))
        await entered.wait()
        task.cancel('native cancellation')
        with pytest.raises(asyncio.CancelledError, match='native cancellation'):
            await task
        await gen.aclose()

    async def failing(owner):
        yield 1
        raise primary

    gen = d.observe('run', 'review.primary')(failing)(ap)
    assert await anext(gen) == 1
    with pytest.raises(ValueError) as caught:
        await anext(gen)
    assert caught.value is primary
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_real_kook_native_entry_conversion_failure_has_trusted_workspace():
    from langbot.pkg.platform.adapters.kook.adapter import KookAdapter
    from langbot.pkg.platform.logger import EventLogger

    ap, ctx = make_ap(), context()
    logger = EventLogger('test', ap, ctx, 'test')
    logger.error = AsyncMock()
    adapter = KookAdapter({'token': 'test-placeholder'}, logger)
    # Invalid native timestamp fails inside the real static converter.
    await adapter._handle_event({'type': 255, 'msg_timestamp': 'CANARY invalid', 'workspace_uuid': str(uuid4())}, 1)
    logger.error.assert_awaited_once()
    failures = [e for e in ap.diagnostics.pending if e['outcome'] == 'failed']
    assert any(e['stage'] == 'convert' for e in failures)
    assert any(e['operation'] == 'platform.receive' for e in failures)
    assert all(e['workspace_uuid'] == ctx.workspace_uuid for e in ap.diagnostics.pending)
    assert all(e['adapter'] == 'kook-omni' for e in ap.diagnostics.pending)
    assert 'CANARY' not in json.dumps(ap.diagnostics.pending)


@pytest.fixture
def boot_stages(monkeypatch):
    from langbot.pkg.core import boot

    stages_run = []

    class Stage:
        async def run(self, app):
            stages_run.append(app)

    # Earlier registry tests clear this shared dictionary; cached imports do not
    # re-register stages. Own the registry per test and restore it on teardown.
    monkeypatch.setattr(boot.stage, 'preregistered_stages', {'LoadConfigStage': Stage, 'GenKeysStage': Stage})
    return stages_run


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['constructor', 'metadata', 'session', 'start'])
@pytest.mark.parametrize('disabled', [False, True])
async def test_real_make_app_optional_initialization_fail_open(monkeypatch, boot_stages, failure, disabled):
    from langbot.pkg.core import boot

    ap = NS(
        instance_config=NS(data={'space': {'url': 'https://example.invalid', 'disable_telemetry': disabled}}),
        initialize=AsyncMock(),
        shutdown=AsyncMock(),
    )
    stages_run = boot_stages
    monkeypatch.setattr(boot.app, 'Application', lambda: ap)
    monkeypatch.setattr(boot, 'stage_order', ['LoadConfigStage', 'GenKeysStage'])
    error = RuntimeError('optional diagnostics')
    if failure == 'constructor':
        monkeypatch.setattr(boot.diagnostics, 'DiagnosticsManager', Mock(side_effect=error))
    elif failure == 'metadata':
        monkeypatch.setattr(
            importlib.metadata, 'version', Mock(side_effect=importlib.metadata.PackageNotFoundError('langbot'))
        )
    else:
        manager = NS(
            start_session=AsyncMock(), start=Mock(), shutdown=AsyncMock(side_effect=RuntimeError('optional cleanup'))
        )
        getattr(manager, 'start_session' if failure == 'session' else 'start').side_effect = error
        monkeypatch.setattr(boot.diagnostics, 'DiagnosticsManager', Mock(return_value=manager))
    assert await boot.make_app(asyncio.get_running_loop()) is ap
    assert len(stages_run) == 2
    ap.initialize.assert_awaited_once()
    ap.shutdown.assert_not_awaited()
    assert getattr(ap, 'diagnostics', None) is None


@pytest.mark.asyncio
async def test_real_make_app_session_cancellation_and_shutdown_failure_preserve_primary(monkeypatch, boot_stages):
    from langbot.pkg.core import boot

    cancelled = asyncio.CancelledError('genuine cancellation')
    ap = NS(
        instance_config=NS(data={'space': {'url': 'https://example.invalid'}}),
        initialize=AsyncMock(),
        shutdown=AsyncMock(side_effect=RuntimeError('shutdown error')),
    )
    manager = NS(start_session=AsyncMock(side_effect=cancelled), start=Mock(), shutdown=AsyncMock())
    monkeypatch.setattr(boot.app, 'Application', lambda: ap)
    monkeypatch.setattr(boot, 'stage_order', ['GenKeysStage'])
    monkeypatch.setattr(boot.diagnostics, 'DiagnosticsManager', Mock(return_value=manager))
    with pytest.raises(asyncio.CancelledError) as caught:
        await boot.make_app(asyncio.get_running_loop())
    assert caught.value is cancelled
    ap.initialize.assert_not_awaited()
    ap.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_make_app_business_failure_not_masked_by_optional_shutdown(monkeypatch, boot_stages):
    from langbot.pkg.core import boot

    primary = ValueError('business startup')
    ap = boot.app.Application()
    ap.instance_config = NS(data={'space': {'url': 'https://example.invalid'}})
    ap.initialize = AsyncMock(side_effect=primary)
    manager = make_ap().diagnostics
    manager.start_session = AsyncMock()
    manager.start = Mock()
    manager.shutdown = AsyncMock(side_effect=RuntimeError('optional shutdown'))
    monkeypatch.setattr(boot.app, 'Application', lambda: ap)
    monkeypatch.setattr(boot.diagnostics, 'DiagnosticsManager', lambda *a, **kw: manager)
    monkeypatch.setattr(boot, 'stage_order', ['GenKeysStage'])

    with pytest.raises(ValueError) as caught:
        await boot.make_app(asyncio.get_running_loop())
    assert caught.value is primary
    manager.shutdown.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
async def test_protocol_rejected_calls_and_unstarted_throw_match_native(disabled):
    ap = make_ap(disabled=disabled)

    async def original(owner):
        try:
            yield 1
        except GeneratorExit:
            yield 2
        yield 3

    async def record(fn, actions):
        gen = fn(ap)
        results = []
        for name, values in actions:
            try:
                results.append(('value', await getattr(gen, name)(*values)))
            except BaseException as exc:
                results.append((type(exc).__name__, str(exc)))
        # Fully exhaust any generator left suspended by a refused close.
        try:
            while True:
                await anext(gen)
        except (StopAsyncIteration, GeneratorExit):
            pass
        return results

    wrapped = d.observe('run', 'review.protocol_matrix')(original)
    for actions in (
        [('aclose', ())],
        [('athrow', (GeneratorExit(),))],
        [('athrow', (ValueError('unstarted'),))],
        [('asend', (7,)), ('__anext__', ()), ('athrow', (ValueError('primary'),))],
        [('__anext__', ()), ('aclose', ()), ('__anext__', ()), ('aclose', ())],
        [('__anext__', ()), ('athrow', (GeneratorExit(),)), ('__anext__', ()), ('aclose', ())],
    ):
        assert await record(wrapped, actions) == await record(original, actions)


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
async def test_native_task_cancel_cleanup_error_wins_without_extra_close(disabled):
    ap = make_ap(disabled=disabled)
    error = ValueError('native cleanup')
    entered = asyncio.Event()

    async def original(owner):
        yield 1
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            raise error

    for fn in (original, d.observe('run', 'review.cancel_cleanup')(original)):
        gen = fn(ap)
        await anext(gen)
        entered.clear()
        task = asyncio.create_task(anext(gen))
        await entered.wait()
        task.cancel()
        with pytest.raises(ValueError) as caught:
            await task
        assert caught.value is error
        await gen.aclose()


@pytest.mark.asyncio
async def test_sdk_b2_handler_consumes_observed_async_generator(tmp_path):
    from langbot_plugin.runtime.io.handler import Handler, ActionResponse
    from langbot_plugin.entities.io.resp import ChunkStatus

    ap = make_ap()
    handler = Handler(NS(), file_storage_dir=str(tmp_path))
    handler._send_message = AsyncMock()

    @d.observe('api', 'host.review_stream', ap=ap)
    async def stream(data):
        yield ActionResponse.success({'business': 'unchanged'})

    handler.actions['review_stream'] = stream
    await handler._handle_action({'seq_id': 1, 'action': 'review_stream', 'data': {}})
    responses = [call.args[0] for call in handler._send_message.await_args_list]
    assert len(responses) == 2
    assert responses[0].data == {'business': 'unchanged'}
    assert [response.chunk_status for response in responses] == [ChunkStatus.CONTINUE, ChunkStatus.END]
    assert [e['outcome'] for e in ap.diagnostics.pending] == ['started', 'succeeded']
