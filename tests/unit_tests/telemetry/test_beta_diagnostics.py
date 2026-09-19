"""Content-free diagnostics contract and lifecycle regression tests."""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from langbot.pkg.telemetry import diagnostics as d


def manager(version='4.11.0-beta.2', **config):
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'space': {'url': 'https://example.invalid', **config}}))
    ap.diagnostics = d.DiagnosticsManager(ap, version=version, instance_id='instance-test', capacity=4)
    return ap.diagnostics


def test_release_gate_and_privacy():
    assert not manager('4.11.0').enabled
    assert manager().enabled
    assert manager('4.11.0b2').enabled
    assert not manager(disable_telemetry=True).enabled
    assert not manager(disable_beta_diagnostics=True).enabled
    m = manager()
    m.emit(
        'api',
        'test.operation',
        'failed',
        attributes={'prompt': 'CANARY', 'plugin_id': 'CANARY', 'attempts': 1},
        error=ValueError('CANARY https://secret/token'),
        workspace_uuid=str(uuid4()),
    )
    payload = m.pending[0]
    assert 'CANARY' not in json.dumps(payload)
    assert payload['attributes'] == {'attempts': 1}
    assert payload['error_type'] == 'ValueError'
    assert payload['instance_id'] != payload['workspace_uuid']
    assert payload['sample_rate'] == 1


@pytest.mark.asyncio
async def test_disabled_boundary_skips_all_projection(monkeypatch):
    m = manager('4.11.0')

    def broken(*args, **kwargs):
        raise AssertionError('diagnostic machinery ran while disabled')

    monkeypatch.setattr(d, 'Span', broken)
    monkeypatch.setattr(d, 'result_outcome', broken)

    class Service:
        ap = m.ap

        @d.observe('api', 'test.disabled', fields=broken)
        async def call(self):
            return 42

        @d.observe('run', 'test.disabled', fields=broken)
        async def stream(self):
            yield 42

    assert await Service().call() == 42
    assert [v async for v in Service().stream()] == [42]
    assert not m.pending


def test_bounds_and_disable_clear():
    m = manager()
    for _ in range(8):
        m.emit('api', 'test.operation', 'succeeded')
    assert len(m.pending) == 4
    assert m.counters['dropped'] == 4
    m.ap.instance_config.data['space']['disable_telemetry'] = True
    m.emit('api', 'test.operation', 'succeeded')
    assert not m.pending


@pytest.mark.asyncio
async def test_partial_ack_retries_same_identity_and_drops_rejected():
    m = manager()
    for _ in range(3):
        m.emit('api', 'test.operation', 'succeeded')
    ids = [e['event_id'] for e in m.pending]
    requests = []

    async def handler(req):
        requests.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={
                'code': 200,
                'data': {'accepted_event_ids': [ids[0]], 'rejected': [{'event_id': ids[1], 'code': 'invalid_event'}]},
            },
        )

    m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await m.flush_once()
    assert [e['event_id'] for e in m.pending] == [ids[2]]
    assert m.counters['acked'] == 1
    assert m.counters['dropped'] == 1
    assert requests[0]['schema_version'] == 1
    await m.shutdown(drain_timeout=0)


@pytest.mark.asyncio
async def test_outage_finite_retry_and_slow_credentials():
    m = manager()
    m.max_attempts = 2
    m.emit('run', 'test.operation', 'started')
    calls = []

    async def handler(req):
        calls.append(req)
        return httpx.Response(503)

    m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await m.flush_once()
    await m.flush_once()
    assert not m.pending
    assert m.counters['dropped'] == 1
    assert len(calls) == 2

    async def credentials(workspace):
        await asyncio.sleep(60)

    m.credentials = credentials
    m.request_timeout = 0.01
    m.emit('api', 'test.operation', 'succeeded')
    await asyncio.wait_for(m.flush_once(), 0.2)
    await m.shutdown(drain_timeout=0)


@pytest.mark.asyncio
async def test_inflight_disable_cancels_and_clears():
    m = manager()
    entered = asyncio.Event()

    async def handler(req):
        entered.set()
        await asyncio.sleep(60)

    m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    m.start()
    m.emit('api', 'test.operation', 'succeeded')
    await asyncio.wait_for(entered.wait(), 1)
    m.ap.instance_config.data['space']['disable_beta_diagnostics'] = True
    await asyncio.sleep(0.3)
    assert not m.pending
    await asyncio.wait_for(m.shutdown(drain_timeout=0), 0.5)


@pytest.mark.asyncio
async def test_observe_returns_errors_and_cancellation():
    m = manager()

    class Service:
        ap = m.ap

        @d.observe('api', 'test.operation')
        async def call(self, error=None):
            if error:
                raise error
            return {'secret': 'CANARY'}

    s = Service()
    assert await s.call() == {'secret': 'CANARY'}
    with pytest.raises(ValueError):
        await s.call(ValueError('CANARY'))
    m.pending.clear()
    with pytest.raises(asyncio.CancelledError):
        await s.call(asyncio.CancelledError())
    assert m.pending[-1]['outcome'] == 'cancelled'
    assert 'CANARY' not in json.dumps(m.pending)


@pytest.mark.asyncio
async def test_generator_send_throw_close_and_context_isolation():
    m = manager()
    m.capacity = 30
    closed = []

    class Service:
        ap = m.ap

        @d.observe('run', 'test.operation')
        async def stream(self):
            try:
                value = yield 1
                try:
                    yield value
                except ValueError:
                    yield 3
            finally:
                closed.append(True)

    gen = Service().stream()
    assert await anext(gen) == 1
    assert d.current_span() is None
    assert await gen.asend(7) == 7
    assert await gen.athrow(ValueError('CANARY')) == 3
    await gen.aclose()
    assert closed == [True]
    assert m.pending[-1]['outcome'] == 'cancelled'
    assert d.current_span() is None


@pytest.mark.asyncio
async def test_generator_early_failure_and_explicit_terminal():
    m = manager()

    class Service:
        ap = m.ap

        @d.observe('run', 'test.operation')
        async def stream(self, fail):
            if fail:
                raise ValueError('prepare CANARY')
            d.set_outcome('failed', reason_code='runner_failed')
            yield 1

    with pytest.raises(ValueError):
        await anext(Service().stream(True))
    assert m.pending[-1]['outcome'] == 'failed'
    m.pending.clear()
    assert [v async for v in Service().stream(False)] == [1]
    assert m.pending[-1]['outcome'] == 'failed'


@pytest.mark.asyncio
async def test_projection_fault_does_not_replace_business_return(monkeypatch):
    m = manager()

    def broken(*args, **kwargs):
        raise RuntimeError('CANARY projection')

    monkeypatch.setattr(d, 'result_outcome', broken)

    class Service:
        ap = m.ap

        @d.observe('api', 'test.projection_fault')
        async def call(self):
            return 42

    assert await Service().call() == 42
    assert m.pending[-1]['outcome'] == 'succeeded'


@pytest.mark.asyncio
async def test_workspace_batches_and_credential_failure_are_anonymous():
    m = manager()
    workspaces = [str(uuid4()), str(uuid4())]
    for workspace in workspaces:
        m.emit('api', 'test.operation', 'succeeded', workspace_uuid=workspace)
    requests = []

    async def broken(workspace):
        raise RuntimeError('CANARY credentials')

    m.credentials = broken

    async def handler(request):
        data = json.loads(request.content)
        requests.append((data, dict(request.headers)))
        return httpx.Response(
            200,
            json={'code': 200, 'data': {'accepted_event_ids': [e['event_id'] for e in data['events']], 'rejected': []}},
        )

    m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await m.flush_once()
    await m.flush_once()
    assert len(requests) == 2
    assert [request[0]['events'][0]['workspace_uuid'] for request in requests] == workspaces
    assert all('authorization' not in headers for _, headers in requests)
    assert not m.pending
    await m.shutdown(drain_timeout=0)


@pytest.mark.asyncio
async def test_summary_is_interval_delta_and_ack_replay_is_idempotent():
    m = manager()
    m.capacity = 20
    m.emit('api', 'test.operation', 'succeeded')
    m.report_transport()
    first = m.pending[-1]
    m.report_transport()
    second = m.pending[-1]
    assert first['attributes']['generated'] == 1
    assert second['attributes']['generated'] == 1  # Only first summary itself.
    assert first['event_id'] != second['event_id']
    ids = [e['event_id'] for e in m.pending]
    seen = []

    async def handler(request):
        body = json.loads(request.content)
        seen.append([e['event_id'] for e in body['events']])
        return (
            httpx.Response(503)
            if len(seen) == 1
            else httpx.Response(200, json={'code': 200, 'data': {'accepted_event_ids': ids + ids, 'rejected': []}})
        )

    m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await m.flush_once()
    await m.flush_once()
    assert seen == [ids, ids]
    assert m.counters['acked'] == len(ids)
    assert not m.pending
    await m.shutdown(drain_timeout=0)


@pytest.mark.asyncio
async def test_retention_and_bounded_shutdown():
    m = manager()
    m.emit('api', 'test.operation', 'succeeded')
    m.retention_seconds = -1
    await m.flush_once()
    assert not m.pending and m.counters['dropped'] == 1
    m.retention_seconds = 900

    async def handler(request):
        await asyncio.sleep(60)
        return httpx.Response(503)

    m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    m.emit('api', 'test.operation', 'succeeded')
    await asyncio.wait_for(m.shutdown(drain_timeout=0.01), 0.5)
    assert not m.pending and m.client.is_closed


@pytest.mark.asyncio
async def test_session_marker_restart_and_disable(tmp_path):
    marker = tmp_path / 'session.json'
    m = manager()
    m.marker_path = marker
    await m.start_session()
    assert marker.exists()
    recovered = manager()
    recovered.marker_path = marker
    await recovered.start_session()
    assert recovered.pending[-1]['attributes']['previous_session_unclean'] is True
    recovered.ap.instance_config.data['space']['disable_beta_diagnostics'] = True
    recovered.start()
    await asyncio.sleep(0.2)
    assert not marker.exists()
    await recovered.shutdown(drain_timeout=0)
    await m.shutdown(drain_timeout=0)
