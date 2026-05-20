"""Unit tests for utils platform detection.

Tests cover:
- get_platform() function
- Docker environment detection
- WebSocket plugin runtime mode
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch
from importlib import import_module


def get_platform_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.utils.platform')


class TestGetPlatform:
    """Tests for get_platform function."""

    def test_returns_docker_when_dockerenv_exists(self):
        """Test returns 'docker' when /.dockerenv file exists."""
        platform_module = get_platform_module()

        with patch('os.path.exists', return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                result = platform_module.get_platform()
                assert result == 'docker'

    def test_returns_docker_when_env_var_true(self):
        """Test returns 'docker' when DOCKER_ENV=true."""
        platform_module = get_platform_module()

        with patch('os.path.exists', return_value=False):
            with patch.dict(os.environ, {'DOCKER_ENV': 'true'}, clear=True):
                result = platform_module.get_platform()
                assert result == 'docker'

    def test_returns_sys_platform_when_not_docker(self):
        """Test returns sys.platform when not in Docker."""
        platform_module = get_platform_module()

        with patch('os.path.exists', return_value=False):
            with patch.dict(os.environ, {'DOCKER_ENV': 'false'}, clear=True):
                result = platform_module.get_platform()
                assert result == sys.platform

    def test_returns_sys_platform_when_no_env_var(self):
        """Test returns sys.platform when DOCKER_ENV not set."""
        platform_module = get_platform_module()

        with patch('os.path.exists', return_value=False):
            # Make sure DOCKER_ENV is not set
            env_copy = os.environ.copy()
            if 'DOCKER_ENV' in env_copy:
                del env_copy['DOCKER_ENV']
            with patch.dict(os.environ, env_copy, clear=True):
                result = platform_module.get_platform()
                assert result == sys.platform

    def test_standalone_runtime_default_false(self):
        """Test standalone_runtime defaults to False."""
        platform_module = get_platform_module()

        # Check the module attribute
        assert platform_module.standalone_runtime is False

    def test_use_websocket_returns_standalone_runtime(self):
        """Test use_websocket_to_connect_plugin_runtime returns standalone_runtime."""
        platform_module = get_platform_module()

        result = platform_module.use_websocket_to_connect_plugin_runtime()
        assert result == platform_module.standalone_runtime

    def test_standalone_runtime_can_be_modified(self):
        """Test standalone_runtime can be modified."""
        platform_module = get_platform_module()

        original = platform_module.standalone_runtime

        # Modify
        platform_module.standalone_runtime = True
        assert platform_module.use_websocket_to_connect_plugin_runtime() is True

        # Restore
        platform_module.standalone_runtime = original