"""Helpers for the current AgentRunner config shape."""

from __future__ import annotations

import typing


class ConfigMigration:
    """Configuration helpers for the current AgentRunner shape.

    Responsibilities:
    - Resolve runner ID from ai.runner.id
    - Extract Agent/runner config from ai.runner_config
    - Read current conversation expiry settings
    """

    @staticmethod
    def resolve_runner_id(pipeline_config: dict[str, typing.Any]) -> str | None:
        """Resolve runner ID from current configuration.

        Args:
            pipeline_config: Current configuration container

        Returns:
            Runner ID string, or None if not configured
        """
        ai_config = pipeline_config.get('ai', {}) if isinstance(pipeline_config, dict) else {}
        runner = ai_config.get('runner', {}) if isinstance(ai_config, dict) else {}
        runner_id = runner.get('id') if isinstance(runner, dict) else None
        return runner_id if isinstance(runner_id, str) and runner_id else None

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
        ai_config = pipeline_config.get('ai', {}) if isinstance(pipeline_config, dict) else {}
        runner_configs = ai_config.get('runner_config', {}) if isinstance(ai_config, dict) else {}
        runner_config = runner_configs.get(runner_id, {}) if isinstance(runner_configs, dict) else {}
        return runner_config if isinstance(runner_config, dict) else {}

    @staticmethod
    def get_expire_time(pipeline_config: dict[str, typing.Any]) -> int:
        """Get conversation expire time from configuration.

        Args:
            pipeline_config: Current configuration container

        Returns:
            Expire time in seconds (0 means no expiry)
        """
        ai_config = pipeline_config.get('ai', {}) if isinstance(pipeline_config, dict) else {}
        runner = ai_config.get('runner', {}) if isinstance(ai_config, dict) else {}
        expire_time = runner.get('expire-time', 0) if isinstance(runner, dict) else 0
        return expire_time if isinstance(expire_time, int) else 0
