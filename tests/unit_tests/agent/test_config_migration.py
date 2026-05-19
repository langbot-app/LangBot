"""Tests for agent runner config migration."""
from __future__ import annotations


from langbot.pkg.agent.runner.config_migration import (
    ConfigMigration,
    OLD_RUNNER_TO_PLUGIN_RUNNER_ID,
)


class TestOldRunnerMapping:
    """Tests for OLD_RUNNER_TO_PLUGIN_RUNNER_ID mapping."""

    def test_local_agent_mapping(self):
        """Local-agent should map to official plugin."""
        assert OLD_RUNNER_TO_PLUGIN_RUNNER_ID['local-agent'] == 'plugin:langbot/local-agent/default'

    def test_dify_mapping(self):
        """Dify should map to official plugin."""
        assert OLD_RUNNER_TO_PLUGIN_RUNNER_ID['dify-service-api'] == 'plugin:langbot/dify-agent/default'

    def test_n8n_mapping(self):
        """n8n should map to official plugin."""
        assert OLD_RUNNER_TO_PLUGIN_RUNNER_ID['n8n-service-api'] == 'plugin:langbot/n8n-agent/default'

    def test_coze_mapping(self):
        """Coze should map to official plugin."""
        assert OLD_RUNNER_TO_PLUGIN_RUNNER_ID['coze-api'] == 'plugin:langbot/coze-agent/default'

    def test_all_runners_mapped(self):
        """All old runners should have mapping."""
        expected_runners = [
            'local-agent',
            'dify-service-api',
            'n8n-service-api',
            'coze-api',
            'dashscope-app-api',
            'langflow-api',
            'tbox-app-api',
        ]
        for runner in expected_runners:
            assert runner in OLD_RUNNER_TO_PLUGIN_RUNNER_ID
            mapped = OLD_RUNNER_TO_PLUGIN_RUNNER_ID[runner]
            assert mapped.startswith('plugin:langbot/')
            assert mapped.endswith('/default')


class TestResolveRunnerId:
    """Tests for ConfigMigration.resolve_runner_id."""

    def test_resolve_new_format_runner_id(self):
        """Resolve runner ID from new format."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot/local-agent/default'

    def test_resolve_old_format_runner_name(self):
        """Resolve runner ID from old format."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot/local-agent/default'

    def test_resolve_old_format_plugin_runner(self):
        """Resolve already migrated plugin:* runner."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'plugin:alice/my-agent/custom',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:alice/my-agent/custom'

    def test_resolve_no_runner_config(self):
        """Resolve runner ID when not configured."""
        pipeline_config = {}

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id is None

    def test_resolve_priority_new_over_old(self):
        """New format takes priority over old format."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                    'runner': 'dify-service-api',  # This should be ignored
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot/local-agent/default'


class TestResolveRunnerConfig:
    """Tests for ConfigMigration.resolve_runner_config."""

    def test_resolve_new_format_config(self):
        """Resolve runner config from new format."""
        pipeline_config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'model': 'uuid-123',
                        'max_round': 10,
                    },
                },
            },
        }

        config = ConfigMigration.resolve_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {'model': 'uuid-123', 'max_round': 10}

    def test_resolve_old_format_config(self):
        """Runtime config resolver should not read old format."""
        pipeline_config = {
            'ai': {
                'local-agent': {
                    'model': 'uuid-123',
                    'max_round': 10,
                },
            },
        }

        config = ConfigMigration.resolve_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {}

    def test_resolve_legacy_config_for_migration(self):
        """Migration helper should read old format."""
        pipeline_config = {
            'ai': {
                'local-agent': {
                    'model': 'uuid-123',
                    'max_round': 10,
                },
            },
        }

        config = ConfigMigration.resolve_legacy_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {'model': 'uuid-123', 'max_round': 10}

    def test_resolve_no_config(self):
        """Resolve runner config when not found."""
        pipeline_config = {}

        config = ConfigMigration.resolve_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {}

    def test_resolve_priority_new_over_old(self):
        """New format config takes priority."""
        pipeline_config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'model': 'new-uuid',
                    },
                },
                'local-agent': {
                    'model': 'old-uuid',
                },
            },
        }

        config = ConfigMigration.resolve_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {'model': 'new-uuid'}


class TestGetExpireTime:
    """Tests for ConfigMigration.get_expire_time."""

    def test_get_expire_time_zero(self):
        """Get expire time when zero."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'expire-time': 0,
                },
            },
        }

        expire_time = ConfigMigration.get_expire_time(pipeline_config)
        assert expire_time == 0

    def test_get_expire_time_positive(self):
        """Get expire time when positive."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'expire-time': 3600,
                },
            },
        }

        expire_time = ConfigMigration.get_expire_time(pipeline_config)
        assert expire_time == 3600

    def test_get_expire_time_default(self):
        """Get expire time when not configured."""
        pipeline_config = {}

        expire_time = ConfigMigration.get_expire_time(pipeline_config)
        assert expire_time == 0


class TestGetOldRunnerName:
    """Tests for ConfigMigration.get_old_runner_name."""

    def test_get_old_runner_name_mapped(self):
        """Get old runner name for mapped runner ID."""
        old_name = ConfigMigration.get_old_runner_name('plugin:langbot/local-agent/default')
        assert old_name == 'local-agent'

    def test_get_old_runner_name_not_mapped(self):
        """Get old runner name for unmapped runner ID."""
        old_name = ConfigMigration.get_old_runner_name('plugin:alice/my-agent/custom')
        assert old_name is None
