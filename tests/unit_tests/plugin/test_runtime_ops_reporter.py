"""Tests for the Cloud plugin runtime ops sample reporter.

Covers the frozen Core -> Space sample contract (C2):
- Runtime /healthz URL derivation from the control WebSocket URL
- Disablement without a runtime WebSocket URL / outside the cloud edition
- Sample assembly from connector internals (desired states, failures, health)
- Best-effort upload semantics (non-2xx and transport failures never raise)
- The pushed payload never carries the runtime control token
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from langbot.pkg.plugin.runtime_ops import RuntimeOpsReporter
from langbot_plugin.entities.io.context import PluginExecutionMode
from langbot_plugin.runtime.security import PLUGIN_RUNTIME_CONTROL_TOKEN_ENV

_CONTROL_PLANE_TOKEN_ENV = 'LANGBOT_SPACE_CONTROL_PLANE_TOKEN'

_DEFAULT_WS_URL = 'ws://langbot_plugin_runtime:5400/control/ws'


def make_policy() -> SimpleNamespace:
    return SimpleNamespace(model_dump=lambda: {'max_workers': 32, 'max_cpus': 0.25})


def make_connector(
    *,
    desired_states: dict | None = None,
    failures: dict | None = None,
    identities: dict | None = None,
    connected: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        runtime_profile='shared',
        worker_policy=make_policy(),
        _known_desired_states=desired_states if desired_states is not None else {},
        _installation_failures=failures if failures is not None else {},
        _reconcile_summary={
            'last_started_at': '2026-10-01T07:11:00Z',
            'last_duration_ms': 1234,
            'last_ok': True,
            'failed_installations': 0,
            'missing_artifacts': 0,
        },
        handler=SimpleNamespace(_installation_bindings=identities if identities is not None else {}),
        _runtime_available=lambda: connected,
    )


def make_app(
    *,
    runtime_ws_url: str | None = _DEFAULT_WS_URL,
    runtime_ops: dict | None = None,
    space_url: str = 'https://space.example',
    deployment_mode: str = 'cloud',
    edition: str = 'cloud',
    connector: SimpleNamespace | None = None,
) -> SimpleNamespace:
    plugin: dict = {}
    if runtime_ws_url is not None:
        plugin['runtime_ws_url'] = runtime_ws_url
    if runtime_ops is not None:
        plugin['runtime_ops'] = runtime_ops
    return SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(
            data={
                'plugin': plugin,
                'space': {'url': space_url},
                'system': {'instance_id': 'inst-1', 'edition': edition},
            }
        ),
        deployment=SimpleNamespace(mode=deployment_mode),
        plugin_connector=connector if connector is not None else make_connector(),
    )


def make_desired_state(workspace_uuid: str, mode: PluginExecutionMode, *, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=enabled,
        execution_mode=mode,
        binding=SimpleNamespace(workspace_uuid=workspace_uuid),
    )


class TestHealthUrlDerivation:
    @pytest.mark.parametrize(
        ('ws_url', 'expected'),
        [
            ('ws://langbot_plugin_runtime:5400/control/ws', 'http://langbot_plugin_runtime:5400/healthz'),
            ('wss://runtime.example/control/ws', 'https://runtime.example/healthz'),
            ('wss://runtime.example:8443/control/ws', 'https://runtime.example:8443/healthz'),
            ('ws://127.0.0.1:5400', 'http://127.0.0.1:5400/healthz'),
            ('  ws://runtime.example:5400/control/ws  ', 'http://runtime.example:5400/healthz'),
        ],
    )
    def test_derives_health_url(self, ws_url: str, expected: str):
        reporter = RuntimeOpsReporter(make_app(runtime_ws_url=ws_url))

        assert reporter.health_url == expected

    @pytest.mark.parametrize('ws_url', ['', None, 'http://runtime.example:5400', 'not a url'])
    def test_rejects_non_websocket_url(self, ws_url):
        reporter = RuntimeOpsReporter(make_app(runtime_ws_url=ws_url))

        assert reporter.health_url is None


class TestEnablement:
    def test_disabled_without_runtime_websocket_url(self):
        reporter = RuntimeOpsReporter(make_app(runtime_ws_url=None))

        assert reporter.enabled is False

    def test_disabled_on_non_cloud_deployment(self):
        reporter = RuntimeOpsReporter(make_app(deployment_mode='oss'))

        assert reporter.enabled is False

    def test_explicit_disable_on_cloud(self):
        reporter = RuntimeOpsReporter(make_app(runtime_ops={'enabled': False}))

        assert reporter.enabled is False

    def test_enabled_by_default_on_cloud(self):
        reporter = RuntimeOpsReporter(make_app())

        assert reporter.enabled is True
        assert reporter.interval_seconds == 30.0
        assert reporter.timeout_seconds == 10.0
        assert reporter.max_failures == 5


class TestSampleAssembly:
    def test_build_payload_matches_contract(self):
        desired = {
            'inst-dedicated': make_desired_state('ws-1', PluginExecutionMode.DEDICATED),
            'inst-shared-off': make_desired_state(
                'ws-2', PluginExecutionMode.SHARED_CERTIFIED, enabled=False
            ),
            'inst-shared-on': make_desired_state('ws-3', PluginExecutionMode.SHARED_CERTIFIED),
        }
        failures = {
            'inst-dedicated': {
                'installation_uuid': 'inst-dedicated',
                'error_code': 'worker_launch_failed',
                'message': 'boom\nstack line',
            },
            'inst-shared-off': {
                'installation_uuid': 'inst-shared-off',
                'error_code': 'dependency_prepare_failed',
                'message': 'prepare failed',
            },
        }
        identities = {
            'inst-dedicated': (
                None,
                SimpleNamespace(plugin_author='acme', plugin_name='dedicated-plugin'),
            ),
        }
        connector = make_connector(desired_states=desired, failures=failures, identities=identities)
        reporter = RuntimeOpsReporter(make_app(connector=connector))
        health = {'live': True, 'runtime': {'version': '0.7.6'}, 'shared_pool': {'workers': 12}}

        payload = reporter.build_payload(health)

        assert set(payload) == {'event', 'kind', 'instance_uuid', 'generated_at', 'core', 'health', 'failures'}
        assert payload['event'] == 'runtime_ops_sample'
        assert payload['kind'] == 'aggregate'
        assert payload['instance_uuid'] == 'inst-1'
        assert payload['generated_at'].endswith('Z')
        # The health blob is forwarded verbatim.
        assert payload['health'] is health

        core = payload['core']
        assert core['edition'] == 'cloud'
        assert core['connected'] is True
        assert core['runtime_profile'] == 'shared'
        assert core['worker_policy'] == {'max_workers': 32, 'max_cpus': 0.25}
        assert core['desired_states'] == {
            'total': 3,
            'enabled': 2,
            'by_mode': {'dedicated': 1, 'shared-runtime-v1': 2},
        }
        assert core['reconcile'] == {
            'last_started_at': '2026-10-01T07:11:00Z',
            'last_duration_ms': 1234,
            'last_ok': True,
            'failed_installations': 0,
            'missing_artifacts': 0,
        }

        assert len(payload['failures']) == 2
        first = payload['failures'][0]
        assert first['workspace_uuid'] == 'ws-1'
        assert first['installation_uuid'] == 'inst-dedicated'
        assert first['plugin_author'] == 'acme'
        assert first['plugin_name'] == 'dedicated-plugin'
        assert first['execution_mode'] == 'dedicated'
        assert first['error_code'] == 'worker_launch_failed'
        assert first['message'] == 'boom stack line'
        assert first['observed_at'].endswith('Z')
        second = payload['failures'][1]
        assert second['workspace_uuid'] == 'ws-2'
        assert second['plugin_author'] == ''
        assert second['plugin_name'] == ''
        assert second['execution_mode'] == 'shared-runtime-v1'

    def test_failures_capped_by_max_failures(self):
        failures = {
            f'inst-{index}': {
                'installation_uuid': f'inst-{index}',
                'error_code': 'worker_launch_failed',
                'message': 'boom',
            }
            for index in range(8)
        }
        connector = make_connector(failures=failures)
        reporter = RuntimeOpsReporter(make_app(runtime_ops={'max_failures': 3}, connector=connector))

        payload = reporter.build_payload({'live': True})

        assert len(payload['failures']) == 3

    def test_disconnected_connector_reports_not_connected(self):
        connector = make_connector(connected=False)
        reporter = RuntimeOpsReporter(make_app(connector=connector))

        payload = reporter.build_payload({'live': False})

        assert payload['core']['connected'] is False


class TestUpload:
    @pytest.mark.asyncio
    async def test_successful_post_increments_sent(self):
        reporter = RuntimeOpsReporter(make_app())
        reporter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'code': 0}))
        )

        await reporter._post({'event': 'runtime_ops_sample'})

        assert reporter.get_stats() == {'sent_total': 1, 'dropped_total': 0, 'last_error': None}
        await reporter.stop()

    @pytest.mark.asyncio
    async def test_non_2xx_increments_dropped_without_raising(self):
        reporter = RuntimeOpsReporter(make_app())
        reporter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(503, text='unavailable'))
        )

        await reporter._post({'event': 'runtime_ops_sample'})

        stats = reporter.get_stats()
        assert stats['sent_total'] == 0
        assert stats['dropped_total'] == 1
        assert '503' in stats['last_error']
        await reporter.stop()

    @pytest.mark.asyncio
    async def test_transport_exception_increments_dropped_without_raising(self):
        def raise_connect_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('connection refused')

        reporter = RuntimeOpsReporter(make_app())
        reporter._client = httpx.AsyncClient(transport=httpx.MockTransport(raise_connect_error))

        await reporter._post({'event': 'runtime_ops_sample'})

        stats = reporter.get_stats()
        assert stats['dropped_total'] == 1
        assert 'connection refused' in stats['last_error']
        await reporter.stop()


def test_payload_never_contains_a_control_token(monkeypatch):
    monkeypatch.setenv(PLUGIN_RUNTIME_CONTROL_TOKEN_ENV, 'runtime-control-secret')
    monkeypatch.setenv(_CONTROL_PLANE_TOKEN_ENV, 'space-control-plane-secret')
    reporter = RuntimeOpsReporter(make_app())

    payload = reporter.build_payload({'live': True})
    serialized = json.dumps(payload)

    assert 'runtime-control-secret' not in serialized
    assert 'space-control-plane-secret' not in serialized
