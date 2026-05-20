"""
Unit tests for ProxyManager.

Tests proxy configuration from environment and config.
"""

from __future__ import annotations

import pytest
import os
from unittest.mock import Mock, patch

from langbot.pkg.utils.proxy import ProxyManager


pytestmark = pytest.mark.asyncio


class TestProxyManager:
    """Tests for ProxyManager class."""

    def _create_mock_app(self, proxy_config: dict = None):
        """Create mock app with proxy config."""
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {'proxy': proxy_config or {}}
        return mock_app

    def test_init_creates_empty_proxies(self):
        """ProxyManager initializes with empty forward_proxies."""
        mock_app = self._create_mock_app()
        pm = ProxyManager(mock_app)

        assert pm.forward_proxies == {}

    async def test_initialize_reads_env_variables(self):
        """initialize reads HTTP_PROXY from environment."""
        mock_app = self._create_mock_app()

        with patch.dict(os.environ, {'HTTP_PROXY': 'http://env-proxy:8080', 'HTTPS_PROXY': 'https://env-proxy:8443'}):
            pm = ProxyManager(mock_app)
            await pm.initialize()

            assert pm.forward_proxies['http://'] == 'http://env-proxy:8080'
            assert pm.forward_proxies['https://'] == 'https://env-proxy:8443'

    async def test_initialize_reads_lower_case_env(self):
        """initialize reads lower case http_proxy from environment."""
        mock_app = self._create_mock_app()

        with patch.dict(os.environ, {'http_proxy': 'http://lower-proxy:8080'}, clear=True):
            # Clear HTTP_PROXY to test fallback
            if 'HTTP_PROXY' in os.environ:
                del os.environ['HTTP_PROXY']

            pm = ProxyManager(mock_app)
            await pm.initialize()

            assert pm.forward_proxies['http://'] == 'http://lower-proxy:8080'

    async def test_initialize_config_overrides_env(self):
        """Config proxy overrides environment variables."""
        mock_app = self._create_mock_app(proxy_config={
            'http': 'http://config-proxy:8080',
            'https': 'https://config-proxy:8443',
        })

        with patch.dict(os.environ, {'HTTP_PROXY': 'http://env-proxy:8080'}):
            pm = ProxyManager(mock_app)
            await pm.initialize()

            assert pm.forward_proxies['http://'] == 'http://config-proxy:8080'
            assert pm.forward_proxies['https://'] == 'https://config-proxy:8443'

    async def test_initialize_sets_env_variables(self):
        """initialize sets proxy to environment variables."""
        mock_app = self._create_mock_app(proxy_config={
            'http': 'http://test-proxy:8080',
            'https': 'https://test-proxy:8443',
        })

        pm = ProxyManager(mock_app)
        await pm.initialize()

        assert os.environ.get('HTTP_PROXY') == 'http://test-proxy:8080'
        assert os.environ.get('HTTPS_PROXY') == 'https://test-proxy:8443'

    async def test_initialize_handles_empty_config(self):
        """initialize handles empty proxy config."""
        mock_app = self._create_mock_app(proxy_config={})

        with patch.dict(os.environ, clear=True):
            pm = ProxyManager(mock_app)
            await pm.initialize()

            assert pm.forward_proxies['http://'] is None
            assert pm.forward_proxies['https://'] is None

    async def test_initialize_handles_no_env_no_config(self):
        """initialize handles no env and no config."""
        mock_app = self._create_mock_app(proxy_config={})

        # Clear proxy env vars
        env_backup = {}
        for key in ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy']:
            env_backup[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        try:
            pm = ProxyManager(mock_app)
            await pm.initialize()

            assert pm.forward_proxies['http://'] is None
            assert pm.forward_proxies['https://'] is None
        finally:
            # Restore env
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_get_forward_proxies_returns_copy(self):
        """get_forward_proxies returns a copy of the dict."""
        mock_app = self._create_mock_app()
        pm = ProxyManager(mock_app)
        pm.forward_proxies = {'http://': 'http://test:8080'}

        result = pm.get_forward_proxies()

        assert result == pm.forward_proxies
        assert result is not pm.forward_proxies  # Different object

    def test_get_forward_proxies_modification_safe(self):
        """Modifying returned dict doesn't affect internal state."""
        mock_app = self._create_mock_app()
        pm = ProxyManager(mock_app)
        pm.forward_proxies = {'http://': 'http://test:8080'}

        result = pm.get_forward_proxies()
        result['http://'] = 'http://modified:9999'

        assert pm.forward_proxies['http://'] == 'http://test:8080'

    async def test_initialize_http_only_config(self):
        """initialize handles http-only config."""
        mock_app = self._create_mock_app(proxy_config={
            'http': 'http://http-only:8080',
        })

        # Clear any existing proxy env vars
        env_backup = {}
        for key in ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy']:
            env_backup[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        try:
            pm = ProxyManager(mock_app)
            await pm.initialize()

            assert pm.forward_proxies['http://'] == 'http://http-only:8080'
            assert pm.forward_proxies['https://'] is None
        finally:
            # Restore env
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value
