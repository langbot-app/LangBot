"""Tests for pipeline config migration to new runner format."""

from __future__ import annotations

import json

from langbot.pkg.agent.runner.config_migration import ConfigMigration


class TestMigratePipelineConfig:
    """Tests for ConfigMigration.migrate_pipeline_config."""

    def test_migrate_old_local_agent_config(self):
        """Old local-agent config should migrate to plugin format."""
        old_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                    'expire-time': 0,
                },
                'local-agent': {
                    'model': {'primary': 'model-uuid', 'fallbacks': []},
                    'knowledge-base': 'kb-uuid',
                    'prompt': [{'role': 'system', 'content': 'Hello'}],
                },
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(old_config)

        # Should have new format
        assert migrated['ai']['runner']['id'] == 'plugin:langbot/local-agent/default'
        assert 'runner' not in migrated['ai']['runner'] or migrated['ai']['runner'].get('runner') != 'local-agent'

        # Config should be in runner_config
        assert 'plugin:langbot/local-agent/default' in migrated['ai']['runner_config']
        assert migrated['ai']['runner_config']['plugin:langbot/local-agent/default']['knowledge-bases'] == ['kb-uuid']
        assert 'knowledge-base' not in migrated['ai']['runner_config']['plugin:langbot/local-agent/default']
        assert 'max-round' not in migrated['ai']['runner_config']['plugin:langbot/local-agent/default']

        # Expire-time preserved
        assert migrated['ai']['runner']['expire-time'] == 0

    def test_migrate_old_dify_service_api_config(self):
        """Old dify-service-api config should migrate to dify-agent plugin."""
        old_config = {
            'ai': {
                'runner': {
                    'runner': 'dify-service-api',
                    'expire-time': 300,
                },
                'dify-service-api': {
                    'base-url': 'https://api.dify.ai/v1',
                    'api-key': 'test-key',
                    'app-type': 'chat',
                },
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(old_config)

        assert migrated['ai']['runner']['id'] == 'plugin:langbot/dify-agent/default'
        assert 'plugin:langbot/dify-agent/default' in migrated['ai']['runner_config']
        assert migrated['ai']['runner_config']['plugin:langbot/dify-agent/default']['api-key'] == 'test-key'
        assert migrated['ai']['runner']['expire-time'] == 300

    def test_new_format_config_stays_unchanged(self):
        """New format config should not change."""
        new_config = {
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

        migrated = ConfigMigration.migrate_pipeline_config(new_config)

        # Should remain unchanged
        assert migrated['ai']['runner']['id'] == 'plugin:langbot/local-agent/default'
        assert migrated['ai']['runner_config']['plugin:langbot/local-agent/default']['custom-option'] == 10

    def test_new_format_local_agent_config_normalizes_legacy_kb_key(self):
        """Migration should normalize legacy KB aliases before runtime."""
        config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'knowledge-base': 'kb-legacy',
                    },
                },
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(config)
        runner_config = migrated['ai']['runner_config']['plugin:langbot/local-agent/default']

        assert runner_config == {'knowledge-bases': ['kb-legacy']}

    def test_migrate_all_old_runners(self):
        """All old runner names should be migrated."""
        old_runners = [
            'local-agent',
            'dify-service-api',
            'n8n-service-api',
            'coze-api',
            'dashscope-app-api',
            'langflow-api',
            'tbox-app-api',
        ]

        expected_ids = [
            'plugin:langbot/local-agent/default',
            'plugin:langbot/dify-agent/default',
            'plugin:langbot/n8n-agent/default',
            'plugin:langbot/coze-agent/default',
            'plugin:langbot/dashscope-agent/default',
            'plugin:langbot/langflow-agent/default',
            'plugin:langbot/tbox-agent/default',
        ]

        for old_runner, expected_id in zip(old_runners, expected_ids):
            config = {
                'ai': {
                    'runner': {'runner': old_runner, 'expire-time': 0},
                    old_runner: {'test-key': 'test-value'},
                },
            }
            migrated = ConfigMigration.migrate_pipeline_config(config)
            assert migrated['ai']['runner']['id'] == expected_id
            assert expected_id in migrated['ai']['runner_config']

    def test_migrate_empty_config(self):
        """Empty config should not break."""
        config = {}
        migrated = ConfigMigration.migrate_pipeline_config(config)
        assert migrated == {}

    def test_migrate_config_without_ai_section(self):
        """Config without ai section should not break."""
        config = {'trigger': {}}
        migrated = ConfigMigration.migrate_pipeline_config(config)
        assert 'trigger' in migrated

    def test_expire_time_preserved(self):
        """expire-time should be preserved during migration."""
        old_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                    'expire-time': 3600,
                },
                'local-agent': {},
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(old_config)
        assert migrated['ai']['runner']['expire-time'] == 3600


class TestDefaultPipelineConfig:
    """Tests for default-pipeline-config.json format."""

    def test_default_config_is_new_format(self):
        """Default pipeline template should use the new runner config shape."""
        from langbot.pkg.utils import paths as path_utils

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Should have new format
        assert 'ai' in config
        assert 'runner' in config['ai']
        assert 'id' in config['ai']['runner']
        assert config['ai']['runner']['id'] == ''

        # Plugin runner selection and config defaults are rendered at creation
        # time from installed AgentRunner metadata.
        assert 'runner_config' in config['ai']
        assert config['ai']['runner_config'] == {}

        # Should NOT have old local-agent key
        assert 'local-agent' not in config['ai']

    def test_default_config_does_not_hardcode_plugin_schema(self):
        """Default template should not duplicate plugin-provided config schema."""
        from langbot.pkg.utils import paths as path_utils

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        assert config['ai']['runner_config'] == {}


class TestResolveRunnerIdAliases:
    """Tests for runner id alias resolution."""

    def test_resolve_new_format_id(self):
        """resolve_runner_id should work with new format."""
        config = {
            'ai': {
                'runner': {'id': 'plugin:test/my-runner/default'},
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id == 'plugin:test/my-runner/default'

    def test_resolve_old_format_runner(self):
        """resolve_runner_id should map old format to plugin ID."""
        config = {
            'ai': {
                'runner': {'runner': 'local-agent'},
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id == 'plugin:langbot/local-agent/default'

    def test_resolve_plugin_format_in_runner_field(self):
        """resolve_runner_id should handle plugin:* in runner field."""
        config = {
            'ai': {
                'runner': {'runner': 'plugin:langbot/local-agent/default'},
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id == 'plugin:langbot/local-agent/default'

    def test_resolve_new_format_priority(self):
        """New format id should take priority over old runner field."""
        config = {
            'ai': {
                'runner': {
                    'id': 'plugin:new-runner/default',
                    'runner': 'local-agent',  # Old field, should be ignored
                },
            },
        }
        runner_id = ConfigMigration.resolve_runner_id(config)
        assert runner_id == 'plugin:new-runner/default'


class TestResolveRunnerConfig:
    """Tests for runtime runner config resolution."""

    def test_resolve_new_format_config(self):
        """resolve_runner_config should read from runner_config."""
        config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot/local-agent/default': {'custom-option': 20},
                },
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot/local-agent/default')
        assert runner_config['custom-option'] == 20

    def test_resolve_old_format_config(self):
        """resolve_runner_config should not read old ai.local-agent at runtime."""
        config = {
            'ai': {
                'local-agent': {'max-round': 15, 'custom-option': 20},
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot/local-agent/default')
        assert runner_config == {}

    def test_resolve_legacy_runner_config_for_migration(self):
        """resolve_legacy_runner_config should read old ai.local-agent for migration."""
        config = {
            'ai': {
                'local-agent': {'max-round': 15, 'custom-option': 20},
            },
        }
        runner_config = ConfigMigration.resolve_legacy_runner_config(config, 'plugin:langbot/local-agent/default')
        assert runner_config == {'custom-option': 20}

    def test_resolve_new_format_priority(self):
        """New format runner_config should take priority."""
        config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot/local-agent/default': {'custom-option': 25},
                },
                'local-agent': {'max-round': 10, 'custom-option': 10},  # Old, should be ignored
            },
        }
        runner_config = ConfigMigration.resolve_runner_config(config, 'plugin:langbot/local-agent/default')
        assert runner_config['custom-option'] == 25
