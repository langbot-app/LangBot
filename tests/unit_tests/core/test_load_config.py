"""Unit tests for core stages load_config _apply_env_overrides_to_config.

Tests cover:
- Environment variable parsing and path conversion
- Type conversion (bool, int, float, string)
- List handling (comma-separated)
- Dict type skipping
- Missing key creation
"""
from __future__ import annotations

import os
from unittest.mock import patch
from importlib import import_module


def get_load_config_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.core.stages.load_config')


class TestApplyEnvOverridesToConfig:
    """Tests for _apply_env_overrides_to_config function."""

    def test_override_string_value(self):
        """Test overriding an existing string config value."""
        load_config = get_load_config_module()

        cfg = {'system': {'name': 'default'}}
        env = {'SYSTEM__NAME': 'custom_name'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['name'] == 'custom_name'

    def test_override_int_value(self):
        """Test overriding an int value with proper conversion."""
        load_config = get_load_config_module()

        cfg = {'concurrency': {'pipeline': 5}}
        env = {'CONCURRENCY__PIPELINE': '10'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['concurrency']['pipeline'] == 10
        assert isinstance(result['concurrency']['pipeline'], int)

    def test_override_int_value_invalid_conversion(self):
        """Test that invalid int conversion keeps string value."""
        load_config = get_load_config_module()

        cfg = {'concurrency': {'pipeline': 5}}
        env = {'CONCURRENCY__PIPELINE': 'not_a_number'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        # Falls back to string when conversion fails
        assert result['concurrency']['pipeline'] == 'not_a_number'

    def test_override_bool_value_true(self):
        """Test overriding bool value with 'true' string."""
        load_config = get_load_config_module()

        cfg = {'system': {'enable': False}}
        env = {'SYSTEM__ENABLE': 'true'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['enable'] is True

    def test_override_bool_value_false(self):
        """Test overriding bool value with 'false' string."""
        load_config = get_load_config_module()

        cfg = {'system': {'enable': True}}
        env = {'SYSTEM__ENABLE': 'false'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['enable'] is False

    def test_override_bool_value_various_true_forms(self):
        """Test that '1', 'yes', 'on' are treated as true."""
        load_config = get_load_config_module()

        cfg = {'system': {'flag': False}}

        for true_val in ['1', 'yes', 'on', 'TRUE']:
            env = {'SYSTEM__FLAG': true_val}
            with patch.dict(os.environ, env, clear=True):
                result = load_config._apply_env_overrides_to_config(cfg.copy())
                assert result['system']['flag'] is True

    def test_override_float_value(self):
        """Test overriding float value with proper conversion."""
        load_config = get_load_config_module()

        cfg = {'system': {'timeout': 1.5}}
        env = {'SYSTEM__TIMEOUT': '2.5'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['timeout'] == 2.5
        assert isinstance(result['system']['timeout'], float)

    def test_override_list_value(self):
        """Test that comma-separated string converts to list."""
        load_config = get_load_config_module()

        cfg = {'system': {'disabled_adapters': ['adapter1']}}
        env = {'SYSTEM__DISABLED_ADAPTERS': 'aiocqhttp,dingtalk,telegram'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['disabled_adapters'] == ['aiocqhttp', 'dingtalk', 'telegram']

    def test_override_list_value_empty_items(self):
        """Test that empty items in comma-separated list are filtered."""
        load_config = get_load_config_module()

        cfg = {'system': {'disabled_adapters': []}}
        env = {'SYSTEM__DISABLED_ADAPTERS': 'a,,b,,,c'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        # Empty items should be filtered out
        assert result['system']['disabled_adapters'] == ['a', 'b', 'c']

    def test_skip_dict_type_override(self):
        """Test that dict type values are skipped."""
        load_config = get_load_config_module()

        cfg = {'plugin': {'settings': {'nested': 'value'}}}
        env = {'PLUGIN__SETTINGS': 'should_not_apply'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        # Dict type should not be overridden
        assert result['plugin']['settings'] == {'nested': 'value'}

    def test_create_new_key_when_missing(self):
        """Test that missing keys are created as strings."""
        load_config = get_load_config_module()

        cfg = {'system': {}}
        env = {'SYSTEM__NEW_KEY': 'new_value'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['new_key'] == 'new_value'

    def test_create_nested_path(self):
        """Test that intermediate dict is created for nested path."""
        load_config = get_load_config_module()

        cfg = {}
        env = {'NEW__SECTION__KEY': 'value'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['new']['section']['key'] == 'value'

    def test_skip_non_uppercase_env_vars(self):
        """Test that non-uppercase env vars are skipped."""
        load_config = get_load_config_module()

        cfg = {'system': {'name': 'default'}}
        env = {'system__name': 'should_not_apply'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['name'] == 'default'

    def test_skip_env_vars_without_double_underscore(self):
        """Test that env vars without __ are skipped."""
        load_config = get_load_config_module()

        cfg = {'system': {'name': 'default'}}
        env = {'SYSTEMNAME': 'should_not_apply'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['name'] == 'default'

    def test_nested_config_path(self):
        """Test overriding deeply nested config."""
        load_config = get_load_config_module()

        cfg = {'level1': {'level2': {'level3': 'original'}}}
        env = {'LEVEL1__LEVEL2__LEVEL3': 'overridden'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['level1']['level2']['level3'] == 'overridden'

    def test_non_dict_current_breaks(self):
        """Test that path navigation stops when current is not dict."""
        load_config = get_load_config_module()

        cfg = {'system': 'not_a_dict'}
        env = {'SYSTEM__NAME': 'should_not_apply'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        # Should remain unchanged since 'system' is not a dict
        assert result == {'system': 'not_a_dict'}

    def test_empty_config(self):
        """Test that empty config dict is handled."""
        load_config = get_load_config_module()

        cfg = {}
        env = {'SOME__KEY': 'value'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['some']['key'] == 'value'

    def test_no_matching_env_vars(self):
        """Test that config is unchanged when no matching env vars."""
        load_config = get_load_config_module()

        cfg = {'system': {'name': 'default'}}
        env = {'OTHER_VAR': 'value'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result == cfg

    def test_multiple_env_vars_override(self):
        """Test multiple env vars applied in order."""
        load_config = get_load_config_module()

        cfg = {
            'system': {'name': 'default', 'enable': True},
            'concurrency': {'pipeline': 5}
        }
        env = {
            'SYSTEM__NAME': 'custom',
            'SYSTEM__ENABLE': 'false',
            'CONCURRENCY__PIPELINE': '10'
        }

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['system']['name'] == 'custom'
        assert result['system']['enable'] is False
        assert result['concurrency']['pipeline'] == 10

    def test_webhook_prefix_override(self):
        """Test overriding webhook_prefix via environment variable."""
        load_config = get_load_config_module()

        cfg = {'api': {'port': 5300, 'webhook_prefix': 'http://127.0.0.1:5300', 'extra_webhook_prefix': ''}}
        env = {'API__WEBHOOK_PREFIX': 'https://example.com:8080'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['api']['webhook_prefix'] == 'https://example.com:8080'

    def test_extra_webhook_prefix_override(self):
        """Test overriding extra_webhook_prefix via environment variable."""
        load_config = get_load_config_module()

        cfg = {'api': {'port': 5300, 'webhook_prefix': 'http://127.0.0.1:5300', 'extra_webhook_prefix': ''}}
        env = {'API__EXTRA_WEBHOOK_PREFIX': 'https://extra.example.com'}

        with patch.dict(os.environ, env, clear=True):
            result = load_config._apply_env_overrides_to_config(cfg)

        assert result['api']['extra_webhook_prefix'] == 'https://extra.example.com'