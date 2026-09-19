"""Real Quart registration boundaries with content-canary payloads."""

import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.group import AuthType, RouterGroup
from langbot.pkg.telemetry import diagnostics as d


class Recorder:
    enabled = True

    def __init__(self):
        self.events = []

    def emit(self, kind, operation, outcome, **fields):
        # A real transport projects the exception class, never its message.
        error = fields.pop('error', None)
        if error is not None:
            fields['error_type'] = type(error).__name__
        self.events.append(dict(kind=kind, operation=operation, outcome=outcome, **fields))


class Routes(RouterGroup):
    path = '/management'
    name = 'management'

    async def initialize(self):
        @self.route('/ok/<identifier>', auth_type=AuthType.NONE)
        async def success(identifier):
            self.ap.seen.append(d.current_span())
            return self.success({'secret': identifier})

        @self.route('/business', auth_type=AuthType.NONE)
        async def business():
            return self.fail('private-error-code', 'private-error-message')

        @self.route('/auth')
        async def authenticated():
            raise AssertionError('must not run')

        @self.route('/error', auth_type=AuthType.NONE)
        async def error():
            raise ValueError('private-exception-message')

        @self.route('/cancel', auth_type=AuthType.NONE)
        async def cancel():
            raise asyncio.CancelledError('private-cancel-message')

        @self.route('/stream', auth_type=AuthType.NONE)
        async def stream():
            async def body():
                self.ap.seen.append(d.current_span())
                yield b'private-stream-chunk'
                self.ap.seen.append(d.current_span())

            return quart.Response(body())


async def setup(manager=True):
    app = quart.Quart(__name__)
    ap = SimpleNamespace(seen=[])
    if manager is True:
        manager = Recorder()
    if manager is not None:
        ap.diagnostics = manager
    routes = Routes(ap, app)
    await routes.initialize()
    return app, ap, routes


@pytest.mark.asyncio
async def test_http_success_uses_code_identity_not_path_or_payload():
    app, ap, _ = await setup()
    response = await app.test_client().get(
        '/management/ok/private-id?token=private-query', headers={'Authorization': 'private-token'}
    )
    assert (await response.get_json())['data']['secret'] == 'private-id'
    assert [e['outcome'] for e in ap.diagnostics.events] == ['started', 'succeeded']
    event = ap.diagnostics.events[-1]
    assert event['source'] == 'http'
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:-]{0,127}', event['operation'])
    assert ap.seen[0] is not None
    assert d.current_span() is None
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'path,status,outcome', [('business', 200, 'failed'), ('auth', 401, 'rejected'), ('error', 500, 'failed')]
)
async def test_http_business_auth_and_exception_outcomes(path, status, outcome):
    app, ap, _ = await setup()
    response = await app.test_client().get('/management/' + path)
    assert response.status_code == status
    assert ap.diagnostics.events[-1]['outcome'] == outcome
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
async def test_http_cancellation_propagates():
    app, ap, _ = await setup()
    async with app.test_request_context('/management/cancel'):
        with pytest.raises(asyncio.CancelledError):
            await app.full_dispatch_request()
    assert ap.diagnostics.events[-1]['outcome'] == 'cancelled'
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_http_auth_cancellation_not_reinterpreted_as_api_key():
    app, ap, routes = await setup()
    routes._authenticate_support_admin = AsyncMock(return_value=None)
    routes._authenticate_account = AsyncMock(side_effect=asyncio.CancelledError())
    async with app.test_request_context('/management/auth', headers={'Authorization': 'Bearer private-token'}):
        with pytest.raises(asyncio.CancelledError):
            await app.full_dispatch_request()
    assert ap.diagnostics.events[-1]['outcome'] == 'cancelled'


@pytest.mark.asyncio
async def test_http_stream_has_parent_context_without_consumer_leak():
    app, ap, _ = await setup()
    async with app.test_request_context('/management/stream'):
        response = await app.full_dispatch_request()
    assert [e['outcome'] for e in ap.diagnostics.events] == ['started']
    assert d.current_span() is None
    async with response.response as body:
        iterator = body.__aiter__()
        assert await anext(iterator) == b'private-stream-chunk'
        assert d.current_span() is None
        assert ap.seen[-1] is not None
        with pytest.raises(StopAsyncIteration):
            await anext(iterator)
    assert ap.seen[0] is ap.seen[1]
    assert ap.diagnostics.events[-1]['outcome'] == 'succeeded'
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'manager', [None, SimpleNamespace(enabled=False, emit=lambda *a, **kw: pytest.fail('disabled emission'))]
)
async def test_absent_disabled_manager_preserves_result_without_context(manager):
    app, ap, _ = await setup(manager)
    response = await app.test_client().get('/management/ok/private-id')
    assert response.status_code == 200
    assert ap.seen == [None]


@pytest.mark.asyncio
async def test_broken_diagnostic_emit_never_masks_operation():
    class Broken(Recorder):
        def emit(self, *args, **kwargs):
            raise RuntimeError('diagnostics broken')

    app, _, _ = await setup(Broken())
    response = await app.test_client().get('/management/ok/private-id')
    assert response.status_code == 200
    async with app.test_request_context('/management/cancel'):
        with pytest.raises(asyncio.CancelledError):
            await app.full_dispatch_request()
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_anonymous_handlers_have_distinct_stable_code_operations():
    app, ap, routes = await setup()

    @routes.route('/items/<identifier>', auth_type=AuthType.NONE, methods=['GET'])
    async def _(identifier):
        return routes.success()

    @routes.route('/items/<identifier>', auth_type=AuthType.NONE, methods=['POST'])
    async def _(identifier):
        return routes.success()

    @routes.route('/other', auth_type=AuthType.NONE)
    async def _():
        return routes.success()

    await app.test_client().get('/management/items/private-id')
    await app.test_client().post('/management/items/private-id')
    await app.test_client().get('/management/other')
    operations = [e['operation'] for e in ap.diagnostics.events if e['outcome'] == 'started']
    assert len(set(operations)) == 3
    assert all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:-]{0,127}', op) for op in operations)
    assert 'private-' not in json.dumps(ap.diagnostics.events)
