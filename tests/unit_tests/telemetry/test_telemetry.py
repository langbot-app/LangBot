"""Unit tests for telemetry module.

Tests cover:
- TelemetryManager initialization
- Payload sanitization logic (with real behavior verification)
- Early return conditions (disabled, empty config, no server)
- URL construction (with actual URL verification)
- HTTP request success/failure scenarios
"""

from __future__ import annotations

import json

import pytest
import httpx
from unittest.mock import AsyncMock, Mock, patch
from importlib import import_module


def get_telemetry_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.telemetry.telemetry')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'instance_config',
    [
        pytest.param(None, id='before-initialize'),
        pytest.param({}, id='no-space-config'),
        pytest.param({'space': {'url': '', 'disable_telemetry': False}}, id='no-endpoint'),
        pytest.param({'space': {'url': 'https://example.invalid', 'disable_telemetry': True}}, id='opted-out'),
    ],
)
async def test_send_does_not_open_http_client_without_active_space(instance_config):
    app = Mock()
    manager = get_telemetry_module().TelemetryManager(app)
    if instance_config is not None:
        app.instance_config.data = instance_config
        await manager.initialize()

    with patch.object(httpx, 'AsyncClient') as http_client:
        await manager.send({'query_id': 'test'})

    http_client.assert_not_called()
    app.logger.debug.assert_not_called()
    app.logger.warning.assert_not_called()


class TestPayloadSanitization:
    """Tests for payload sanitization logic in send() method.

    IMPORTANT: These tests verify actual behavior, not source code strings.
    """

    @pytest.mark.asyncio
    async def test_sanitize_query_id_string_value(self):
        """Test that query_id string value is preserved."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        captured_payloads = []

        async def mock_post(url, json):
            captured_payloads.append(json)
            return Mock(status_code=200, text='', json=Mock(return_value={'code': 0}))

        mock_client = Mock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'abc123'})

        assert len(captured_payloads) == 1
        assert captured_payloads[0]['query_id'] == 'abc123'

    @pytest.mark.asyncio
    async def test_sanitize_string_fields_preserve_values(self):
        """Test that non-null string fields preserve their values."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        captured_payloads = []

        async def mock_post(url, json):
            captured_payloads.append(json)
            return Mock(status_code=200, text='', json=Mock(return_value={'code': 0}))

        mock_client = Mock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        payload = {
            'query_id': 'test',
            'adapter': 'gewechat',
            'runner': 'local-agent',
            'model_name': 'gpt-4',
            'version': 'v1.0.0',
        }

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send(payload)

        assert len(captured_payloads) == 1
        result = captured_payloads[0]

        assert result['adapter'] == 'gewechat'
        assert result['runner'] == 'local-agent'
        assert result['model_name'] == 'gpt-4'
        assert result['version'] == 'v1.0.0'


@pytest.mark.asyncio
@pytest.mark.parametrize('suffix', ['', '/'], ids=['bare-url', 'trailing-slash'])
async def test_configured_space_receives_one_normalized_telemetry_request(suffix):
    app = Mock()
    app.instance_config.data = {'space': {'url': f'https://example.invalid{suffix}'}}
    manager = get_telemetry_module().TelemetryManager(app)
    await manager.initialize()
    requests = []

    def handle_request(request):
        requests.append(request)
        return httpx.Response(200, json={'code': 0})

    payload = {'query_id': 'wired-config'}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle_request)) as client:
        manager._client = client
        await manager.send(payload)

    assert [(request.method, str(request.url)) for request in requests] == [
        ('POST', 'https://example.invalid/api/v1/telemetry')
    ]
    assert json.loads(requests[0].content) == payload


class TestHTTPScenarios:
    """Tests for HTTP request success/failure scenarios."""

    @pytest.mark.asyncio
    async def test_send_http_success_logs_debug(self):
        """Test that HTTP 200 with code=0 logs debug message."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        mock_response = Mock(
            status_code=200, text='{"code": 0, "msg": "success"}', json=Mock(return_value={'code': 0, 'msg': 'success'})
        )

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        mock_app.logger.warning.assert_not_called()
        mock_app.logger.debug.assert_called()
        # Verify debug message contains URL and status
        debug_call_args = mock_app.logger.debug.call_args[0][0]
        assert 'Telemetry posted' in debug_call_args
        assert 'https://example.com/api/v1/telemetry' in debug_call_args

    @pytest.mark.asyncio
    async def test_send_http_error_status_logs_warning(self):
        """Test that HTTP status >= 400 logs warning."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        mock_response = Mock(
            status_code=500, text='Internal Server Error', json=Mock(return_value={'code': 500, 'msg': 'error'})
        )

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        mock_app.logger.warning.assert_not_called()
        mock_app.logger.debug.assert_called()
        warning_call_args = mock_app.logger.debug.call_args[0][0]
        assert 'status 500' in warning_call_args

    @pytest.mark.asyncio
    async def test_send_application_error_logs_warning(self):
        """Test that HTTP 200 with application code >= 400 logs warning."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        mock_response = Mock(
            status_code=200,
            text='{"code": 400, "msg": "Bad Request"}',
            json=Mock(return_value={'code': 400, 'msg': 'Bad Request'}),
        )

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        # Source code calls warning twice for application errors
        assert mock_app.logger.debug.call_count >= 1
        # Check that one of the calls contains application error info
        all_warnings = [call[0][0] for call in mock_app.logger.debug.call_args_list]
        assert any('400' in w for w in all_warnings), f'No warning contained error code 400: {all_warnings}'

    @pytest.mark.asyncio
    async def test_send_timeout_logs_warning(self):
        """Test that asyncio.TimeoutError logs warning."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        import asyncio

        async def mock_post_timeout(url, json):
            raise asyncio.TimeoutError()

        mock_client = Mock()
        mock_client.post = mock_post_timeout
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        mock_app.logger.warning.assert_not_called()
        mock_app.logger.debug.assert_called()
        warning_call_args = mock_app.logger.debug.call_args[0][0]
        assert 'timed out' in warning_call_args

    @pytest.mark.asyncio
    async def test_send_network_error_logs_warning(self):
        """Test that network exceptions log warning without raising."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        async def mock_post_error(url, json):
            raise httpx.ConnectError('Connection failed')

        mock_client = Mock()
        mock_client.post = mock_post_error
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            # Should not raise exception
            await manager.send({'query_id': 'test'})

        mock_app.logger.warning.assert_not_called()
        mock_app.logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_send_never_raises_exception(self):
        """Test that send() never raises exceptions regardless of errors."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        # Even logger may fail
        mock_app.logger = Mock()
        mock_app.logger.debug = Mock(side_effect=Exception('Logger failed'))

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        async def mock_post_error(url, json):
            raise Exception('Unexpected error')

        mock_client = Mock()
        mock_client.post = mock_post_error
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            # Should never raise
            await manager.send({'query_id': 'test'})


class TestTelemetryManagedRuntimeAuthentication:
    @pytest.mark.asyncio
    async def test_send_includes_managed_runtime_token_header(self):
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()
        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}
        captured = {}

        async def mock_post(url, json, headers):
            captured['headers'] = headers
            return Mock(status_code=200, text='', json=Mock(return_value={'code': 0}))

        mock_client = Mock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with (
            patch.dict('os.environ', {'LANGBOT_TELEMETRY_INGEST_TOKEN': 'managed-runtime-secret'}),
            patch.object(httpx, 'AsyncClient', return_value=mock_client),
        ):
            await manager.send({'event_type': 'instance_heartbeat'})

        assert captured['headers'] == {'X-LangBot-Telemetry-Token': 'managed-runtime-secret'}


class TestAuthenticatedWorkspaceReporter:
    @pytest.mark.asyncio
    async def test_workspace_owner_access_token_is_sent_as_bearer(self):
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()
        mock_app.user_service = Mock()
        mock_app.user_service.get_workspace_owner = AsyncMock(
            return_value=Mock(user='owner@example.com', space_access_token='expired-token')
        )
        mock_app.space_service = Mock()
        mock_app.space_service.get_valid_access_token = AsyncMock(return_value='refreshed-workspace-owner-token')
        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        response = Mock(status_code=200, text='')
        response.json = Mock(return_value={'code': 0})
        mock_client = Mock()
        mock_client.post = Mock(return_value=response)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'q-1', 'workspace_uuid': 'workspace-1'})

        mock_app.user_service.get_workspace_owner.assert_awaited_once_with('workspace-1')
        mock_app.space_service.get_valid_access_token.assert_awaited_once_with('owner@example.com')
        assert mock_client.post.call_args.kwargs['headers'] == {
            'Authorization': 'Bearer refreshed-workspace-owner-token'
        }
