"""Helpers for the current AgentRunner config shape."""

from __future__ import annotations

import typing


class ConfigMigration:
    """Configuration helper for agent runner IDs.

    Responsibilities:
    - Resolve runner ID from ai.runner.id
    - Extract current Agent/runner config from ai.runner_config
    - Keep the current config container shape stable on save
    """

    @staticmethod
    def resolve_runner_id(pipeline_config: dict[str, typing.Any]) -> str | None:
        """Resolve runner ID from current configuration.

        Args:
            pipeline_config: Current configuration container

        Returns:
            Runner ID string, or None if not configured
        """
        ai_config = pipeline_config.get('ai', {})
        runner_config = ai_config.get('runner', {})

        runner_id = runner_config.get('id')
        if runner_id:
            return runner_id

        return None

    @staticmethod
    def resolve_runner_config(
        pipeline_config: dict[str, typing.Any],
        runner_id: str,
    ) -> dict[str, typing.Any]:
        """Resolve Agent/runner configuration from the current container.

        Args:
            pipeline_config: Current configuration container
            runner_id: Resolved runner ID

        Returns:
            Runner configuration dict (empty if not found)
        """
        ai_config = pipeline_config.get('ai', {})

        runner_configs = ai_config.get('runner_config', {})
        if runner_id in runner_configs:
            return runner_configs[runner_id]

        return {}

    @staticmethod
    def get_expire_time(pipeline_config: dict[str, typing.Any]) -> int:
        """Get conversation expire time from configuration.

        Args:
            pipeline_config: Current configuration container

        Returns:
            Expire time in seconds (0 means no expiry)
        """
        ai_config = pipeline_config.get('ai', {})
        runner_config = ai_config.get('runner', {})
        return runner_config.get('expire-time', 0)

    @staticmethod
    def migrate_pipeline_config(pipeline_config: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Normalize the current config container before saving.

        Args:
            pipeline_config: Original configuration

        Returns:
            Configuration with explicit ai.runner and ai.runner_config containers
        """
        new_config = dict(pipeline_config)
        if 'ai' not in new_config:
            return new_config

        ai_config = dict(new_config.get('ai', {}))

        runner_config = dict(ai_config.get('runner', {}))
        runner_configs = dict(ai_config.get('runner_config', {}))

        ai_config['runner'] = runner_config
        ai_config['runner_config'] = runner_configs
        new_config['ai'] = ai_config

        return new_config
