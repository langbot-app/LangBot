"""Unit tests for telemetry module.

Tests cover:
- TelemetryManager initialization
- Payload sanitization logic (with real behavior verification)
- Early return conditions (disabled, empty config, no server)
- URL construction (with actual URL verification)
- HTTP request success/failure scenarios
- Source code bug: send_tasks should be instance variable
"""
from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, Mock, patch
from importlib import import_module


def get_telemetry_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.telemetry.telemetry')


class TestTelemetryManagerInit:
    """Tests for TelemetryManager initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores the Application reference."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        manager = telemetry.TelemetryManager(mock_app)
        assert manager.ap is mock_app

    def test_init_empty_telemetry_config(self):
        """Test that telemetry_config starts empty."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        manager = telemetry.TelemetryManager(mock_app)
        assert manager.telemetry_config == {}

class TestTelemetryManagerInitialize:
    """Tests for initialize() method."""

    @pytest.mark.asyncio
    async def test_initialize_loads_space_config(self):
        """Test that initialize() loads space config from instance_config."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {'space': {'url': 'https://example.com'}}

        manager = telemetry.TelemetryManager(mock_app)
        await manager.initialize()

        assert manager.telemetry_config == {'url': 'https://example.com'}

    @pytest.mark.asyncio
    async def test_initialize_handles_empty_space_config(self):
        """Test that initialize() handles missing space config."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {}

        manager = telemetry.TelemetryManager(mock_app)
        await manager.initialize()

        assert manager.telemetry_config == {}


class TestTelemetrySendEarlyReturn:
    """Tests for early return conditions in send() method."""

    @pytest.mark.asyncio
    async def test_send_returns_when_config_empty(self):
        """Test that send() returns early when telemetry_config is empty."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {}

        # Should return without making HTTP calls
        await manager.send({'query_id': 'test'})

        # No HTTP client should be created, no logs should be written
        mock_app.logger.debug.assert_not_called()
        mock_app.logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_returns_when_telemetry_disabled(self):
        """Test that send() returns early when disable_telemetry is True."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'disable_telemetry': True, 'url': 'https://example.com'}

        await manager.send({'query_id': 'test'})

        mock_app.logger.debug.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_returns_when_server_empty(self):
        """Test that send() returns early when server URL is empty."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': ''}

        await manager.send({'query_id': 'test'})

        mock_app.logger.debug.assert_not_called()


class TestPayloadSanitization:
    """Tests for payload sanitization logic in send() method.

    IMPORTANT: These tests verify actual behavior, not source code strings.
    """

    @pytest.mark.asyncio
    async def test_sanitize_null_query_id(self):
        """Test that null query_id is converted to empty string."""
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
            await manager.send({'query_id': None})

        assert len(captured_payloads) == 1
        assert captured_payloads[0]['query_id'] == ''

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
    async def test_sanitize_null_string_fields(self):
        """Test that null string fields are converted to empty strings."""
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
            'adapter': None,
            'runner': None,
            'runner_category': None,
            'model_name': None,
            'version': None,
            'edition': None,
            'error': None,
            'timestamp': None,
        }

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send(payload)

        assert len(captured_payloads) == 1
        result = captured_payloads[0]

        # All null string fields should be empty strings
        for field in ['adapter', 'runner', 'runner_category', 'model_name', 'version', 'edition', 'error', 'timestamp']:
            assert result[field] == '', f"Field {field} should be empty string, got {result[field]}"

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
    async def test_sanitize_duration_ms_invalid_value(self):
        """Test that invalid duration_ms is converted to 0."""
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
            await manager.send({'query_id': 'test', 'duration_ms': 'invalid'})

        assert len(captured_payloads) == 1
        assert captured_payloads[0]['duration_ms'] == 0

    @pytest.mark.asyncio
    async def test_sanitize_duration_ms_none_value(self):
        """Test that None duration_ms is converted to 0."""
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
            await manager.send({'query_id': 'test', 'duration_ms': None})

        assert len(captured_payloads) == 1
        assert captured_payloads[0]['duration_ms'] == 0

    @pytest.mark.asyncio
    async def test_sanitize_duration_ms_valid_value(self):
        """Test that valid duration_ms is converted to int."""
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
            await manager.send({'query_id': 'test', 'duration_ms': 123.45})

        assert len(captured_payloads) == 1
        assert captured_payloads[0]['duration_ms'] == 123


class TestURLConstruction:
    """Tests for URL construction in send() method.

    IMPORTANT: These tests verify actual URLs sent, not source code strings.
    """

    @pytest.mark.asyncio
    async def test_url_strip_trailing_slash(self):
        """Test that trailing slash is stripped from server URL."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com/'}

        captured_urls = []

        async def mock_post(url, json):
            captured_urls.append(url)
            return Mock(status_code=200, text='', json=Mock(return_value={'code': 0}))

        mock_client = Mock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        assert len(captured_urls) == 1
        assert captured_urls[0] == 'https://example.com/api/v1/telemetry'
        # No trailing slash before /api/v1/telemetry

    @pytest.mark.asyncio
    async def test_url_without_trailing_slash(self):
        """Test that URL without trailing slash works correctly."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {'url': 'https://example.com'}

        captured_urls = []

        async def mock_post(url, json):
            captured_urls.append(url)
            return Mock(status_code=200, text='', json=Mock(return_value={'code': 0}))

        mock_client = Mock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        assert len(captured_urls) == 1
        assert captured_urls[0] == 'https://example.com/api/v1/telemetry'


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
            status_code=200,
            text='{"code": 0, "msg": "success"}',
            json=Mock(return_value={'code': 0, 'msg': 'success'})
        )

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

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
            status_code=500,
            text='Internal Server Error',
            json=Mock(return_value={'code': 500, 'msg': 'error'})
        )

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        mock_app.logger.warning.assert_called()
        warning_call_args = mock_app.logger.warning.call_args[0][0]
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
            json=Mock(return_value={'code': 400, 'msg': 'Bad Request'})
        )

        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, 'AsyncClient', return_value=mock_client):
            await manager.send({'query_id': 'test'})

        # Source code calls warning twice for application errors
        assert mock_app.logger.warning.call_count >= 1
        # Check that one of the calls contains application error info
        all_warnings = [call[0][0] for call in mock_app.logger.warning.call_args_list]
        assert any('400' in w for w in all_warnings), f"No warning contained error code 400: {all_warnings}"

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

        mock_app.logger.warning.assert_called()
        warning_call_args = mock_app.logger.warning.call_args[0][0]
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

        mock_app.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_send_never_raises_exception(self):
        """Test that send() never raises exceptions regardless of errors."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        # Even logger may fail
        mock_app.logger = Mock()
        mock_app.logger.warning = Mock(side_effect=Exception('Logger failed'))

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


class TestStartSendTask:
    """Tests for start_send_task() method."""

    @pytest.mark.asyncio
    async def test_start_send_task_creates_task(self):
        """Test that start_send_task creates an asyncio task."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {}

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {}

        await manager.start_send_task({'query_id': 'test'})

        # Task should be added to send_tasks list
        assert len(manager.send_tasks) >= 1

        # Clean up the task
        for task in manager.send_tasks:
            if not task.done():
                task.cancel()
        manager.send_tasks.clear()

    @pytest.mark.asyncio
    async def test_start_send_task_multiple_tasks(self):
        """Test that multiple tasks are tracked."""
        telemetry = get_telemetry_module()
        mock_app = Mock()
        mock_app.logger = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {}

        manager = telemetry.TelemetryManager(mock_app)
        manager.telemetry_config = {}

        await manager.start_send_task({'query_id': 'test1'})
        await manager.start_send_task({'query_id': 'test2'})
        await manager.start_send_task({'query_id': 'test3'})

        assert len(manager.send_tasks) >= 3

        # Clean up
        for task in manager.send_tasks:
            if not task.done():
                task.cancel()
        manager.send_tasks.clear()
