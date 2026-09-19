"""CORE-DIAG-6: management ownership barriers under a foreign live span."""

import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import quart

from langbot.pkg.api import management_diagnostics as md
from langbot.pkg.api.http.context import (
    ExecutionContext,
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.controller.group import AuthType
from langbot.pkg.api.http.controller.groups.pipelines.embed import EmbedRouterGroup
from langbot.pkg.api.http.controller.groups.pipelines.websocket_chat import WebSocketChatRouterGroup
from langbot.pkg.api.http.service.agent import AgentService
from langbot.pkg.api.mcp.server import LangBotMCPServer
from langbot.pkg.telemetry import diagnostics as d
from tests.unit_tests.api.test_diagnostics_management_http import Recorder, Routes


MODES = ['enabled', 'disabled', 'absent', 'mismatched', 'policy_off', 'beta_off', 'broken']


def app(identity):
    ap = NS(instance_config=NS(data={'space': {'url': 'https://example.invalid'}}))
    ap.diagnostics = d.DiagnosticsManager(ap, version='4.11.0b2', instance_id=identity)
    return ap


def owners(mode):
    a, b = app('instance-A'), app('instance-B')
    b_manager = b.diagnostics
    if mode == 'disabled':
        b.instance_config.data['space']['disable_telemetry'] = True
        b.diagnostics = d.DiagnosticsManager(b, version='4.11.0b2', instance_id='instance-B')
        b_manager = b.diagnostics
    elif mode == 'absent':
        del b.diagnostics
    elif mode == 'mismatched':
        b.diagnostics = a.diagnostics
    elif mode in {'policy_off', 'beta_off'}:
        # Also test an attached structural producer whose enabled flag stays true.
        b.diagnostics = Recorder()
        b.instance_config.data['space']['disable_telemetry' if mode == 'policy_off' else 'disable_beta_diagnostics'] = (
            True
        )
    elif mode == 'broken':
        b.diagnostics = NS(enabled=True, emit=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('broken')))
    ca = ExecutionContext('instance-A', str(uuid4()), 1)
    cb = ExecutionContext('instance-B', str(uuid4()), 1)
    d.privacy.code_value('operation', 'http.isolation.parent')
    parent = d.Span(a.diagnostics, 'api', 'http.isolation.parent', {'workspace_uuid': ca.workspace_uuid})
    return a, b, b_manager, ca, cb, parent


@d.observe('event', 'platform.target2yiri', source='platform', stage='convert')
async def converter(native):
    return native


async def nested(b, cb, seen):
    md.workspace(cb)
    seen.append(d.current_span())
    with md.scope(b, 'websocket.isolation.inner', source='websocket'):
        md.workspace(cb)
        assert await converter(42) == 42
    # Both an inner management boundary and an ownerless converter must be safe.
    assert await converter(43) == 43
    return 44


def assert_isolated(a, b, b_manager, ca, cb, parent, mode):
    assert parent.fields['workspace_uuid'] == ca.workspace_uuid
    assert parent.outcome is None
    assert len(a.diagnostics.pending) == 1  # Only the caller's own start event.
    assert not b_manager.pending if mode != 'enabled' else b_manager.pending
    if isinstance(getattr(b, 'diagnostics', None), Recorder):
        assert b.diagnostics.events == []
    if mode == 'enabled':
        assert all(e['instance_id'] == 'instance-B' for e in b_manager.pending)
        assert all(e['trace_id'] != parent.fields['trace_id'] for e in b_manager.pending)
        assert all(e['workspace_uuid'] != ca.workspace_uuid for e in b_manager.pending)
        assert any(e['workspace_uuid'] == cb.workspace_uuid for e in b_manager.pending)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('shape', ['decorator', 'scope'])
async def test_nested_management_masks_foreign_parent_and_restores_caller(mode, shape):
    a, b, manager, ca, cb, parent = owners(mode)
    seen = []

    @md.observe('http.isolation.endpoint', source='http', ap=b)
    async def endpoint():
        return await nested(b, cb, seen)

    with parent.activate():
        if shape == 'decorator':
            assert await endpoint() == 44
        else:
            with md.scope(b, 'websocket.isolation.outer', source='websocket'):
                assert await nested(b, cb, seen) == 44
        assert d.current_span() is parent
    assert d.current_span() is None
    assert (seen[0] is not None) == (mode == 'enabled')
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
async def test_actual_agent_debug_never_mutates_foreign_workspace(mode):
    a, b, manager, ca, cb, parent = owners(mode)
    service = AgentService(b)
    seen = []

    async def missing(*args):
        await nested(b, cb, seen)
        return None

    service.get_agent = missing
    with parent.activate():
        with pytest.raises(ValueError, match='^Agent not found$'):
            await service.debug_agent(cb, 'private-agent', {})
        assert d.current_span() is parent
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('termination', ['exhaust', 'close', 'error', 'cancel'])
async def test_real_http_body_keeps_barrier_during_advancement_and_cleanup(mode, termination):
    a, b, manager, ca, cb, parent = owners(mode)
    web = quart.Quart(__name__)
    routes = Routes(b, web)
    seen, closed = [], []
    failure = asyncio.CancelledError('private-cancel') if termination == 'cancel' else ValueError('private-error')

    @routes.route('/isolated', auth_type=AuthType.NONE)
    async def endpoint():
        await nested(b, cb, seen)

        async def stream():
            try:
                await nested(b, cb, seen)
                yield b'one'
                if termination in {'cancel', 'error'}:
                    raise failure
                await nested(b, cb, seen)
            finally:
                await nested(b, cb, seen)
                closed.append(True)

        return quart.Response(stream())

    # Construct with no caller parent; the later body consumer has app A's span.
    async with web.test_request_context('/management/isolated'):
        response = await web.full_dispatch_request()
    with parent.activate():
        try:
            async with response.response as body:
                iterator = body.__aiter__()
                assert await anext(iterator) == b'one'
                assert d.current_span() is parent
                if termination != 'close':
                    with pytest.raises((StopAsyncIteration, type(failure))) as caught:
                        await anext(iterator)
                    if termination in {'cancel', 'error'}:
                        assert caught.value is failure
                    else:
                        assert isinstance(caught.value, StopAsyncIteration)
        finally:
            assert d.current_span() is parent
    assert closed == [True]
    assert all((span is not None) == (mode == 'enabled') for span in seen)
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
async def test_real_mcp_registered_tool_masks_foreign_parent(mode):
    a, b, manager, ca, cb, parent = owners(mode)
    seen = []

    async def get_bot(*args, **kwargs):
        return {'value': await nested(b, cb, seen)}

    b.bot_service = NS(get_bot=get_bot)
    server = LangBotMCPServer(b)
    with parent.activate(), patch('langbot.pkg.api.mcp.server._authorized', return_value=cb):
        assert await server.mcp.call_tool('get_bot', {'bot_uuid': 'private-bot'})
        assert d.current_span() is parent
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('group_class', [WebSocketChatRouterGroup, EmbedRouterGroup])
async def test_real_websocket_receive_masks_foreign_parent(mode, group_class):
    a, b, manager, ca, cb, parent = owners(mode)
    group = group_class(b, quart.Quart(__name__))
    connection = NS(is_active=True, connection_id='private-id', send_queue=asyncio.Queue())
    seen = []

    async def handle(*args, **kwargs):
        await nested(b, cb, seen)

    adapter = NS(handle_websocket_message=handle)
    if group_class is WebSocketChatRouterGroup:
        group._revalidate_websocket_authorization = AsyncMock(return_value=cb)
    else:
        group._resolve_connected_bot = AsyncMock(return_value=NS(execution_context=cb))

    async def receive():
        connection.is_active = False
        return '{"type":"message","text":"private-prompt"}'

    with (
        parent.activate(),
        patch('quart.websocket', NS(receive=receive)),
        patch(
            'langbot.pkg.api.http.controller.groups.pipelines.websocket_chat.ws_connection_manager.update_activity',
            new=AsyncMock(),
        ),
    ):
        await group._handle_receive(connection, adapter, NS(execution_context=cb), 'private-token')
        assert d.current_span() is parent
    assert seen
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.parametrize('kind', ['execution', 'request'])
def test_workspace_rejects_foreign_instance_or_foreign_active_span(kind):
    a, b, _, ca, cb, parent = owners('enabled')
    context = cb
    if kind == 'request':
        context = RequestContext(
            cb.instance_uuid,
            1,
            'request',
            'api_key',
            PrincipalContext(PrincipalType.API_KEY),
            WorkspaceContext(cb.workspace_uuid, None, None, frozenset()),
        )
    with md.scope(a, 'http.isolation.annotation', source='http'):
        span = d.current_span()
        md.workspace(context)
        assert 'workspace_uuid' not in span.fields
        md.workspace(ca)
        assert span.fields['workspace_uuid'] == ca.workspace_uuid
        with parent.activate():
            before = dict(parent.fields)
            md.workspace(ca)
            md.workspace(context)
            assert parent.fields == before


def test_structural_recorder_workspace_and_scope_exception_identity():
    recorder = Recorder()
    ap = NS(diagnostics=recorder)
    ctx = ExecutionContext('instance', str(uuid4()), 1)
    error = ValueError('private-error')
    with pytest.raises(ValueError) as caught:
        with md.scope(ap, 'http.isolation.recorder', source='http'):
            md.workspace(ctx)
            assert d.current_span().fields['workspace_uuid'] == ctx.workspace_uuid
            raise error
    assert caught.value is error
    assert recorder.events[-1]['outcome'] == 'failed'
    assert d.current_span() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES[1:])
@pytest.mark.parametrize('termination', ['success', 'error', 'cancel'])
async def test_nested_off_boundary_restores_outer_annotation_and_error(mode, termination):
    a, b, manager, ca, cb, parent = owners(mode)
    error = asyncio.CancelledError('private-cancel') if termination == 'cancel' else ValueError('private-error')

    @md.observe('http.isolation.off', source='http', ap=b)
    async def endpoint():
        await nested(b, cb, [])
        md.outcome('failed')
        if termination != 'success':
            raise error
        return 42

    with parent.activate():
        with md.scope(a, 'http.isolation.outer', source='http'):
            outer = d.current_span()
            if termination == 'success':
                assert await endpoint() == 42
            else:
                with pytest.raises(type(error)) as caught:
                    await endpoint()
                assert caught.value is error
            assert d.current_span() is outer
            md.workspace(ca)
            assert outer.fields['workspace_uuid'] == ca.workspace_uuid
            assert outer.outcome is None
        assert d.current_span() is parent
    assert not manager.pending
    assert [e['operation'] for e in a.diagnostics.pending] == [
        'http.isolation.parent',
        'http.isolation.outer',
        'http.isolation.outer',
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('group_class', [WebSocketChatRouterGroup, EmbedRouterGroup])
async def test_websocket_send_cancel_restores_foreign_parent(mode, group_class):
    a, b, manager, ca, cb, parent = owners(mode)
    group = group_class(b, quart.Quart(__name__))
    connection = NS(is_active=False, send_queue=asyncio.Queue())
    await connection.send_queue.put({'text': 'private-answer'})
    error = asyncio.CancelledError('private-cancel')

    async def send(payload):
        await nested(b, cb, [])
        raise error

    with parent.activate(), patch('quart.websocket', NS(send=send)):
        with pytest.raises(asyncio.CancelledError) as caught:
            await group._handle_send(connection)
        assert caught.value is error
        assert d.current_span() is parent
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', MODES)
async def test_sync_http_body_exhaustion_has_owned_context_without_consumer_leak(mode):
    a, b, manager, ca, cb, parent = owners(mode)
    seen, closed = [], []

    def stream():
        try:
            for value in (b'one', b'two'):
                md.workspace(cb)
                seen.append(d.current_span())
                yield value
        finally:
            seen.append(d.current_span())
            closed.append(True)

    @md.observe('http.isolation.sync_body', source='http', ap=b, http=True)
    async def endpoint():
        return quart.Response(stream())

    response = await endpoint()
    with parent.activate():
        async with response.response as body:
            chunks = []
            async for chunk in body:
                assert d.current_span() is parent
                chunks.append(chunk)
        assert d.current_span() is parent
    assert chunks == [b'one', b'two']
    assert closed == [True]
    assert all((span is not None) == (mode == 'enabled') for span in seen)
    assert_isolated(a, b, manager, ca, cb, parent, mode)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['enabled', 'disabled', 'absent', 'mismatched'])
@pytest.mark.parametrize('failure_stage', ['enter', 'iterator', 'advance', 'exit', None])
async def test_custom_http_body_protocol_and_cancellation_identity(mode, failure_stage):
    from quart.wrappers.response import IterableBody

    a, b, manager, ca, cb, parent = owners(mode)
    error = asyncio.CancelledError('private-body-cancel')
    seen = []

    def visit(stage):
        md.workspace(cb)
        seen.append((stage, d.current_span()))
        if stage == failure_stage:
            raise error

    class Body(IterableBody):
        def __init__(self):
            pass

        async def __aenter__(self):
            visit('enter')
            return self

        def __aiter__(self):
            visit('iterator')
            return self

        async def __anext__(self):
            visit('advance')
            raise StopAsyncIteration

        async def __aexit__(self, *args):
            visit('exit')

    @md.observe('http.isolation.body_protocol', source='http', ap=b, http=True)
    async def endpoint():
        response = quart.Response()
        response.response = Body()
        return response

    response = await endpoint()

    async def consume():
        async with response.response as body:
            assert d.current_span() is parent
            async for _ in body:
                pytest.fail('empty body yielded')

    with parent.activate():
        if failure_stage is None:
            await consume()
        else:
            with pytest.raises(asyncio.CancelledError) as caught:
                await consume()
            assert caught.value is error
        assert d.current_span() is parent
    assert all((span is not None) == (mode == 'enabled') for _, span in seen)
    assert [s for s, _ in seen].count('exit') == (0 if failure_stage in {'enter', 'iterator'} else 1)
    assert_isolated(a, b, manager, ca, cb, parent, mode)
