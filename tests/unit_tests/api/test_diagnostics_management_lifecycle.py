"""HTTP streaming termination, fail-open behavior and real producer privacy."""

import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.agent.runner import errors as runner_errors
from langbot.pkg.api import management_diagnostics as md
from langbot.pkg.api.http.controller.group import AuthType
from langbot.pkg.api.http.controller.groups.agent_debug_stream import debug_stream_response
from langbot.pkg.api.mcp.mount import MCPMount
from langbot.pkg.telemetry import diagnostics as d
from tests.unit_tests.api.test_diagnostics_management_http import Recorder, setup


@pytest.mark.asyncio
@pytest.mark.parametrize('termination', ['close', 'cancel', 'error'])
async def test_stream_termination_preserves_cleanup_and_error(termination):
    app, ap, routes = await setup()
    closed = []

    @routes.route('/end', auth_type=AuthType.NONE)
    async def end():
        async def body():
            try:
                yield b'one'
                if termination == 'error':
                    raise ValueError('private-error')
                if termination == 'cancel':
                    raise asyncio.CancelledError('private-cancel')
                yield b'two'
            finally:
                closed.append(d.current_span())

        return quart.Response(body())

    async with app.test_request_context('/management/end'):
        response = await app.full_dispatch_request()
    if termination == 'close':
        async with response.response as body:
            assert await anext(body.__aiter__()) == b'one'
    else:
        error = ValueError if termination == 'error' else asyncio.CancelledError
        with pytest.raises(error):
            async with response.response as body:
                iterator = body.__aiter__()
                assert await anext(iterator) == b'one'
                await anext(iterator)
    assert len(closed) == 1 and closed[0] is not None
    expected = 'failed' if termination == 'error' else 'cancelled'
    assert [e['outcome'] for e in ap.diagnostics.events] == ['started', expected]
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_debug_ndjson_error_marks_http_business_failure():
    app, ap, routes = await setup()
    service = SimpleNamespace(debug_agent=AsyncMock(side_effect=runner_errors.RunnerNotFoundError('private-error')))

    @routes.route('/ndjson', auth_type=AuthType.NONE)
    async def ndjson():
        return debug_stream_response(service, object(), 'private-agent', {'text': 'private-text'})

    response = await app.test_client().get('/management/ndjson')
    assert response.status_code == 200
    assert json.loads(await response.get_data())['kind'] == 'error'
    assert ap.diagnostics.events[-1]['outcome'] == 'failed'
    assert 'private-' not in json.dumps(ap.diagnostics.events)


@pytest.mark.asyncio
async def test_terminal_diagnostic_failure_preserves_success_and_stream():
    class BrokenFinish(Recorder):
        def emit(self, kind, operation, outcome, **fields):
            if outcome != 'started':
                raise RuntimeError('private-diagnostic-error')
            super().emit(kind, operation, outcome, **fields)

    app, _, _ = await setup(BrokenFinish())
    response = await app.test_client().get('/management/stream')
    assert await response.get_data() == b'private-stream-chunk'
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_real_manager_status_privacy_and_no_network_in_request():
    app, ap, _ = await setup(None)
    ap.instance_config = SimpleNamespace(data={'space': {'url': 'https://example.invalid'}})
    ap.diagnostics = d.DiagnosticsManager(ap, version='4.11.0-beta.2', instance_id='instance-test', capacity=20)
    ap.diagnostics.credentials = AsyncMock(side_effect=AssertionError('must not await credentials'))
    for path in ['ok/private-identifier', 'business', 'auth', 'cancel']:
        async with app.test_request_context('/management/' + path):
            try:
                await app.full_dispatch_request()
            except asyncio.CancelledError:
                pass
    events = list(ap.diagnostics.pending)
    assert len(events) == 8
    assert {e['outcome'] for e in events} == {'started', 'succeeded', 'failed', 'rejected', 'cancelled'}
    assert all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:-]{0,127}', e['operation']) for e in events)
    assert 'private-' not in json.dumps(events)
    ap.diagnostics.credentials.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'config,version',
    [
        ({}, '4.11.0'),
        ({'disable_telemetry': True}, '4.11.0-beta.2'),
        ({'disable_beta_diagnostics': True}, '4.11.0-beta.2'),
    ],
)
async def test_real_manager_disabled_modes_do_not_install_context(config, version):
    app, ap, _ = await setup(None)
    ap.instance_config = SimpleNamespace(data={'space': config})
    ap.diagnostics = d.DiagnosticsManager(ap, version=version, instance_id='instance-test')
    response = await app.test_client().get('/management/ok/private-id')
    assert response.status_code == 200
    assert ap.seen == [None]
    assert not ap.diagnostics.pending


@pytest.mark.asyncio
async def test_mcp_mount_observes_auth_without_headers_or_body():
    ap = SimpleNamespace(
        diagnostics=Recorder(), apikey_service=SimpleNamespace(authenticate_api_key=AsyncMock(return_value=None))
    )
    mount = MCPMount(ap)
    send = AsyncMock()
    fallback = AsyncMock()
    await mount.wrap(fallback)(
        {'type': 'http', 'path': '/mcp/private-path', 'headers': [(b'x-api-key', b'private-token')]}, AsyncMock(), send
    )
    assert send.call_args_list[0].args[0]['status'] == 401
    assert [e['outcome'] for e in ap.diagnostics.events] == ['started', 'rejected']
    assert ap.diagnostics.events[-1]['operation'] == 'mcp.request'
    assert 'private-' not in json.dumps(ap.diagnostics.events)
    fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_debug_boundary_source_inherits_without_duplicate_run():
    recorder = Recorder()
    ap = SimpleNamespace(diagnostics=recorder)

    @md.observe('http.test.debug', source='webui_debug', ap=ap)
    async def debug():
        @d.observe('run', 'runner.run', source='agent', ap=ap)
        async def run():
            return 'private-content'

        return await run()

    assert await debug() == 'private-content'
    assert len([e for e in recorder.events if e['kind'] == 'run' and e['outcome'] == 'started']) == 1
    assert all(e['source'] == 'webui_debug' and e['attributes']['synthetic'] for e in recorder.events)
    assert 'private-' not in json.dumps(recorder.events)
