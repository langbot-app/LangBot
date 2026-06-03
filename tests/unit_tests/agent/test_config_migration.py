"""Tests for current AgentRunner config helpers."""

from __future__ import annotations

from langbot.pkg.agent.runner.config_migration import ConfigMigration


class TestResolveRunnerId:
    """Tests for ConfigMigration.resolve_runner_id."""

    def test_resolve_current_runner_id(self):
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot/local-agent/default'

    def test_does_not_resolve_old_runner_field(self):
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id is None

    def test_resolve_no_runner_config(self):
        runner_id = ConfigMigration.resolve_runner_id({})
        assert runner_id is None


class TestResolveRunnerConfig:
    """Tests for ConfigMigration.resolve_runner_config."""

    def test_resolve_current_config(self):
        pipeline_config = {
            'ai': {
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'model': 'uuid-123',
                        'custom_option': 10,
                    },
                },
            },
        }

        config = ConfigMigration.resolve_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {'model': 'uuid-123', 'custom_option': 10}

    def test_does_not_read_old_runner_block(self):
        pipeline_config = {
            'ai': {
                'local-agent': {
                    'model': 'uuid-123',
                },
            },
        }

        config = ConfigMigration.resolve_runner_config(
            pipeline_config,
            'plugin:langbot/local-agent/default',
        )
        assert config == {}

    def test_resolve_no_config(self):
        config = ConfigMigration.resolve_runner_config(
            {},
            'plugin:langbot/local-agent/default',
        )
        assert config == {}


class TestGetExpireTime:
    """Tests for ConfigMigration.get_expire_time."""

    def test_get_expire_time_zero(self):
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
        expire_time = ConfigMigration.get_expire_time({})
        assert expire_time == 0


class TestNormalizePipelineConfig:
    """Tests for ConfigMigration.migrate_pipeline_config."""

    def test_normalizes_current_containers(self):
        config = {'ai': {}}

        migrated = ConfigMigration.migrate_pipeline_config(config)

        assert migrated == {'ai': {'runner': {}, 'runner_config': {}}}

    def test_preserves_current_config(self):
        config = {
            'ai': {
                'runner': {'id': 'plugin:test/my-runner/default'},
                'runner_config': {
                    'plugin:test/my-runner/default': {'custom-option': 20},
                },
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(config)

        assert migrated['ai']['runner']['id'] == 'plugin:test/my-runner/default'
        assert migrated['ai']['runner_config']['plugin:test/my-runner/default']['custom-option'] == 20

    def test_does_not_migrate_old_runner_blocks(self):
        config = {
            'ai': {
                'runner': {'runner': 'local-agent'},
                'local-agent': {'model': 'old-model'},
            },
        }

        migrated = ConfigMigration.migrate_pipeline_config(config)

        assert 'id' not in migrated['ai']['runner']
        assert migrated['ai']['local-agent'] == {'model': 'old-model'}
