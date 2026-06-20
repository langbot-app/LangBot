"""Helpers for the current AgentRunner config shape."""

from __future__ import annotations

import typing


LEGACY_RUNNER_ID_MAP: dict[str, str] = {
    'local-agent': 'plugin:langbot/local-agent/default',
    'dify-service-api': 'plugin:langbot/dify-agent/default',
    'n8n-service-api': 'plugin:langbot/n8n-agent/default',
    'coze-api': 'plugin:langbot/coze-agent/default',
    'dashscope-app-api': 'plugin:langbot/dashscope-agent/default',
    'deerflow-api': 'plugin:langbot/deerflow-agent/default',
    'langflow-api': 'plugin:langbot/langflow-agent/default',
    'tbox-app-api': 'plugin:langbot/tbox-agent/default',
    'weknora-api': 'plugin:langbot/weknora-agent/default',
}


class ConfigMigration:
    """Configuration helper for agent runner IDs.

    Responsibilities:
    - Resolve runner ID from ai.runner.id
    - Migrate legacy ai.runner.runner + ai.<runner-name> blocks
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

        legacy_runner = runner_config.get('runner')
        if isinstance(legacy_runner, str):
            return LEGACY_RUNNER_ID_MAP.get(legacy_runner)

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

        legacy_runner = ConfigMigration._legacy_runner_name_for_id(runner_id)
        if legacy_runner and isinstance(ai_config.get(legacy_runner), dict):
            return ConfigMigration._normalize_legacy_runner_config(
                legacy_runner,
                ai_config[legacy_runner],
            )

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

        legacy_runner = runner_config.get('runner')
        mapped_runner_id = None
        if isinstance(legacy_runner, str):
            mapped_runner_id = LEGACY_RUNNER_ID_MAP.get(legacy_runner)

        if mapped_runner_id and not runner_config.get('id'):
            runner_config = {
                key: value
                for key, value in runner_config.items()
                if key != 'runner'
            }
            runner_config['id'] = mapped_runner_id

        if mapped_runner_id and mapped_runner_id not in runner_configs:
            legacy_config = ai_config.get(legacy_runner)
            if isinstance(legacy_config, dict):
                runner_configs[mapped_runner_id] = ConfigMigration._normalize_legacy_runner_config(
                    legacy_runner,
                    legacy_config,
                )

        ai_config['runner'] = runner_config
        ai_config['runner_config'] = runner_configs
        if mapped_runner_id and legacy_runner in ai_config:
            ai_config.pop(legacy_runner, None)
        new_config['ai'] = ai_config

        return new_config

    @staticmethod
    def _legacy_runner_name_for_id(runner_id: str) -> str | None:
        for legacy_runner, mapped_runner_id in LEGACY_RUNNER_ID_MAP.items():
            if mapped_runner_id == runner_id:
                return legacy_runner
        return None

    @staticmethod
    def _normalize_legacy_runner_config(
        legacy_runner: str,
        legacy_config: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        """Normalize legacy runner config blocks to current plugin schema quirks."""
        normalized = dict(legacy_config)

        if legacy_runner == 'local-agent':
            model = normalized.get('model')
            if isinstance(model, str):
                normalized['model'] = {
                    'primary': model,
                    'fallbacks': [],
                }
            knowledge_base = normalized.pop('knowledge-base', None)
            if 'knowledge-bases' not in normalized and isinstance(knowledge_base, str):
                normalized['knowledge-bases'] = [] if knowledge_base in {'', '__none__', '__none'} else [knowledge_base]

        return normalized
