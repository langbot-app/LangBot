"""Tests for persisted AgentRunner config shape."""

from __future__ import annotations

import json

from langbot.pkg.agent.runner.config_migration import ConfigMigration


class TestMigratePipelineConfig:
    """Tests for ConfigMigration.migrate_pipeline_config."""

    def test_current_format_config_stays_unchanged(self):
        config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                    'expire-time': 0,
                },
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'model': {'primary': '', 'fallbacks': []},
                        'custom-option': 10,
                    },
                },
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(config)

        assert migrated['ai']['runner']['id'] == 'plugin:langbot/local-agent/default'
        assert migrated['ai']['runner_config']['plugin:langbot/local-agent/default']['custom-option'] == 10

    def test_old_runner_field_is_mapped(self):
        config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                    'expire-time': 3600,
                },
                'local-agent': {
                    'model': 'old-model',
                },
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(config)

        assert migrated['ai']['runner'] == {
            'expire-time': 3600,
            'id': 'plugin:langbot/local-agent/default',
        }
        assert migrated['ai']['runner_config']['plugin:langbot/local-agent/default'] == {
            'model': {'primary': 'old-model', 'fallbacks': []},
        }
        assert 'local-agent' not in migrated['ai']

    def test_empty_config_is_unchanged(self):
        config = {}
        migrated = ConfigMigration.migrate_pipeline_config(config)
        assert migrated == {}

    def test_config_without_ai_section_is_unchanged(self):
        config = {'trigger': {}}
        migrated = ConfigMigration.migrate_pipeline_config(config)
        assert migrated == {'trigger': {}}


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

    def test_old_runner_field_is_mapped(self):
        config = {
            'ai': {
                'runner': {'runner': 'local-agent'},
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id == 'plugin:langbot/local-agent/default'


class TestResolveRunnerConfig:
    """Tests for runtime runner config resolution."""

    def test_resolve_current_config(self):
        config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot/local-agent/default': {'custom-option': 20},
                },
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot/local-agent/default')
        assert runner_config['custom-option'] == 20

    def test_old_runner_block_is_read(self):
        config = {
            'ai': {
                'local-agent': {'custom-option': 20},
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot/local-agent/default')
        assert runner_config == {'custom-option': 20}
