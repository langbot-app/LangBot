"""Tests for persisted AgentRunner config shape."""

from __future__ import annotations

import json

from langbot.pkg.agent.runner.config_migration import ConfigMigration


class TestDefaultPipelineConfig:
    """Tests for default-pipeline-config.json format."""

    def test_default_config_is_current_format(self):
        from langbot.pkg.utils import paths as path_utils

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        assert 'ai' in config
        assert 'runner' in config['ai']
        assert 'id' in config['ai']['runner']
        assert config['ai']['runner']['id'] == ''
        assert 'runner_config' in config['ai']
        assert config['ai']['runner_config'] == {}
        assert 'local-agent' not in config['ai']


class TestResolveRunnerId:
    """Tests for current runner id resolution."""

    def test_resolve_current_id(self):
        config = {
            'ai': {
                'runner': {'id': 'plugin:test/my-runner/default'},
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id == 'plugin:test/my-runner/default'

    def test_old_runner_field_is_not_supported(self):
        config = {
            'ai': {
                'runner': {'runner': 'local-agent'},
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id is None


class TestResolveRunnerConfig:
    """Tests for runtime runner config resolution."""

    def test_resolve_current_config(self):
        config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {'custom-option': 20},
                },
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot-team/LocalAgent/default')
        assert runner_config['custom-option'] == 20

    def test_old_runner_block_is_not_supported(self):
        config = {
            'ai': {
                'local-agent': {'custom-option': 20},
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot-team/LocalAgent/default')
        assert runner_config == {}
