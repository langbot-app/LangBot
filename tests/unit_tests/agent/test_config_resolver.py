"""Tests for current AgentRunner config resolution."""

from __future__ import annotations

import pytest

from langbot.pkg.agent.runner.config_resolver import RunnerConfigResolver


class TestResolveRunnerId:
    """Tests for RunnerConfigResolver.resolve_runner_id."""

    def test_resolve_current_runner_id(self):
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot-team/LocalAgent/default',
                },
            },
        }

        runner_id = RunnerConfigResolver.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot-team/LocalAgent/default'

    def test_does_not_resolve_legacy_runner_field(self):
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                },
            },
        }

        runner_id = RunnerConfigResolver.resolve_runner_id(pipeline_config)
        assert runner_id is None

    def test_resolve_no_runner_config(self):
        runner_id = RunnerConfigResolver.resolve_runner_id({})
        assert runner_id is None


class TestResolveRunnerConfig:
    """Tests for RunnerConfigResolver.resolve_runner_config."""

    def test_resolve_current_config(self):
        pipeline_config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {
                        'model': 'uuid-123',
                        'custom_option': 10,
                    },
                },
            },
        }

        config = RunnerConfigResolver.resolve_runner_config(
            pipeline_config,
            'plugin:langbot-team/LocalAgent/default',
        )
        assert config == {'model': 'uuid-123', 'custom_option': 10}

    def test_does_not_read_legacy_runner_block(self):
        pipeline_config = {
            'ai': {
                'local-agent': {
                    'model': 'uuid-123',
                },
            },
        }

        config = RunnerConfigResolver.resolve_runner_config(
            pipeline_config,
            'plugin:langbot-team/LocalAgent/default',
        )
        assert config == {}

    def test_resolve_no_config(self):
        config = RunnerConfigResolver.resolve_runner_config(
            {},
            'plugin:langbot-team/LocalAgent/default',
        )
        assert config == {}


class TestGetExpireTime:
    """Tests for RunnerConfigResolver.get_expire_time."""

    def test_get_expire_time_zero(self):
        pipeline_config = {
            'ai': {
                'runner': {
                    'expire-time': 0,
                },
            },
        }

        expire_time = RunnerConfigResolver.get_expire_time(pipeline_config)
        assert expire_time == 0

    def test_get_expire_time_positive(self):
        pipeline_config = {
            'ai': {
                'runner': {
                    'expire-time': 3600,
                },
            },
        }

        expire_time = RunnerConfigResolver.get_expire_time(pipeline_config)
        assert expire_time == 3600


class TestValidateCurrentConfig:
    @pytest.mark.parametrize(
        ('field_name', 'invalid_value'),
        [
            ('enable-all-tools', 0),
            ('enable-all-tools', None),
            ('enable-all-tools', 'false'),
            ('mcp-resource-agent-read-enabled', 0),
            ('mcp-resource-agent-read-enabled', None),
            ('mcp-resource-agent-read-enabled', 'false'),
        ],
    )
    def test_agent_rejects_non_boolean_selected_runner_security_fields(self, field_name, invalid_value):
        config = {
            'runner': {'id': 'plugin:test/runner/default'},
            'runner_config': {
                'plugin:test/runner/default': {
                    field_name: invalid_value,
                }
            },
        }

        with pytest.raises(ValueError, match=f'{field_name}.*boolean'):
            RunnerConfigResolver.validate_agent_config(config)

    @pytest.mark.parametrize(
        ('field_name', 'invalid_value'),
        [
            ('enable-all-tools', 0),
            ('enable-all-tools', None),
            ('enable-all-tools', 'false'),
            ('mcp-resource-agent-read-enabled', 0),
            ('mcp-resource-agent-read-enabled', None),
            ('mcp-resource-agent-read-enabled', 'false'),
        ],
    )
    def test_pipeline_rejects_non_boolean_selected_runner_security_fields(self, field_name, invalid_value):
        config = {
            'ai': {
                'runner': {'id': 'plugin:test/runner/default'},
                'runner_config': {
                    'plugin:test/runner/default': {
                        field_name: invalid_value,
                    }
                },
            }
        }

        with pytest.raises(ValueError, match=f'{field_name}.*boolean'):
            RunnerConfigResolver.validate_pipeline_config(config)

    def test_only_selected_runner_security_fields_are_validated(self):
        config = {
            'runner': {'id': 'plugin:test/selected/default'},
            'runner_config': {
                'plugin:test/selected/default': {'enable-all-tools': False},
                'plugin:test/unselected/default': {'enable-all-tools': 'preserved'},
            },
        }

        assert RunnerConfigResolver.validate_agent_config(config) is config

    @pytest.mark.parametrize('invalid_value', [0, None, 'false'])
    @pytest.mark.parametrize('config_kind', ['agent', 'pipeline'])
    def test_rejects_non_boolean_mcp_resource_enabled(self, config_kind, invalid_value):
        runner_id = 'plugin:test/runner/default'
        runner_config = {'mcp-resources': [{'uri': 'file:///README.md', 'enabled': invalid_value}]}
        if config_kind == 'agent':
            config = {
                'runner': {'id': runner_id},
                'runner_config': {runner_id: runner_config},
            }
            validate = RunnerConfigResolver.validate_agent_config
        else:
            config = {
                'ai': {
                    'runner': {'id': runner_id},
                    'runner_config': {runner_id: runner_config},
                }
            }
            validate = RunnerConfigResolver.validate_pipeline_config

        with pytest.raises(ValueError, match=r'mcp-resources\[0\]\.enabled.*boolean'):
            validate(config)

    @pytest.mark.parametrize('enabled', [True, False])
    def test_accepts_boolean_mcp_resource_enabled(self, enabled):
        runner_config = {'mcp-resources': [{'enabled': enabled}]}

        assert RunnerConfigResolver.validate_runner_security_fields(runner_config) is runner_config

    def test_get_expire_time_default(self):
        expire_time = RunnerConfigResolver.get_expire_time({})
        assert expire_time == 0
