"""Configuration migration for agent runner IDs."""
from __future__ import annotations

import typing

from .id import is_plugin_runner_id


# Mapping from old built-in runner names to official plugin runner IDs
OLD_RUNNER_TO_PLUGIN_RUNNER_ID = {
    'local-agent': 'plugin:langbot/local-agent/default',
    'dify-service-api': 'plugin:langbot/dify-agent/default',
    'n8n-service-api': 'plugin:langbot/n8n-agent/default',
    'coze-api': 'plugin:langbot/coze-agent/default',
    'dashscope-app-api': 'plugin:langbot/dashscope-agent/default',
    'langflow-api': 'plugin:langbot/langflow-agent/default',
    'tbox-app-api': 'plugin:langbot/tbox-agent/default',
}


class ConfigMigration:
    """Configuration migration helper for agent runner IDs.

    Responsibilities:
    - Resolve runner ID from new ai.runner.id or old ai.runner.runner
    - Map old built-in runner names to official plugin runner IDs
    - Extract runtime runner config from ai.runner_config
    - Migrate old ai.<runner-name> blocks into ai.runner_config
    """

    @staticmethod
    def resolve_runner_id(pipeline_config: dict[str, typing.Any]) -> str | None:
        """Resolve runner ID from pipeline configuration.

        Priority:
        1. New format: ai.runner.id (must be plugin:* format)
        2. Old format: ai.runner.runner (mapped to plugin:* if built-in)

        Args:
            pipeline_config: Pipeline configuration dict

        Returns:
            Runner ID string, or None if not configured
        """
        ai_config = pipeline_config.get('ai', {})
        runner_config = ai_config.get('runner', {})

        # Check new format first
        runner_id = runner_config.get('id')
        if runner_id:
            if is_plugin_runner_id(runner_id):
                return runner_id
            # If it's not a plugin ID, try to map it as old runner name
            return OLD_RUNNER_TO_PLUGIN_RUNNER_ID.get(runner_id, runner_id)

        # Check old format
        old_runner_name = runner_config.get('runner')
        if old_runner_name:
            # If already plugin:* format, return directly
            if is_plugin_runner_id(old_runner_name):
                return old_runner_name
            # Map old built-in runner to official plugin ID
            mapped_id = OLD_RUNNER_TO_PLUGIN_RUNNER_ID.get(old_runner_name)
            if mapped_id:
                return mapped_id
            # Return old name if no mapping exists (will error in registry)
            return old_runner_name

        return None

    @staticmethod
    def resolve_runner_config(
        pipeline_config: dict[str, typing.Any],
        runner_id: str,
    ) -> dict[str, typing.Any]:
        """Resolve runner binding configuration from pipeline configuration.

        Runtime code should only read the migrated format. Legacy
        ai.<runner-name> blocks are handled by migration helpers, not by the
        hot path.

        Args:
            pipeline_config: Pipeline configuration dict
            runner_id: Resolved runner ID

        Returns:
            Runner configuration dict (empty if not found)
        """
        ai_config = pipeline_config.get('ai', {})

        # Check new format
        runner_configs = ai_config.get('runner_config', {})
        if runner_id in runner_configs:
            return runner_configs[runner_id]

        return {}

    @staticmethod
    def resolve_legacy_runner_config(
        pipeline_config: dict[str, typing.Any],
        runner_id: str,
    ) -> dict[str, typing.Any]:
        """Resolve old ai.<runner-name> config for migration only."""
        ai_config = pipeline_config.get('ai', {})

        # Try to find old runner name from runner_id
        old_runner_name = None
        for old_name, mapped_id in OLD_RUNNER_TO_PLUGIN_RUNNER_ID.items():
            if mapped_id == runner_id:
                old_runner_name = old_name
                break

        if old_runner_name:
            old_config = ai_config.get(old_runner_name, {})
            if old_config:
                return old_config

        return {}

    @staticmethod
    def get_old_runner_name(runner_id: str) -> str | None:
        """Get old runner name from mapped runner ID.

        Args:
            runner_id: Plugin runner ID

        Returns:
            Old runner name if mapped, None otherwise
        """
        for old_name, mapped_id in OLD_RUNNER_TO_PLUGIN_RUNNER_ID.items():
            if mapped_id == runner_id:
                return old_name
        return None

    @staticmethod
    def get_expire_time(pipeline_config: dict[str, typing.Any]) -> int:
        """Get conversation expire time from configuration.

        Args:
            pipeline_config: Pipeline configuration dict

        Returns:
            Expire time in seconds (0 means no expiry)
        """
        ai_config = pipeline_config.get('ai', {})
        runner_config = ai_config.get('runner', {})
        return runner_config.get('expire-time', 0)

    @staticmethod
    def migrate_pipeline_config(pipeline_config: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Migrate pipeline config to new format.

        This converts old ai.runner.runner and ai.<runner-name> to
        new ai.runner.id and ai.runner_config format.

        Args:
            pipeline_config: Original pipeline configuration

        Returns:
            Migrated pipeline configuration
        """
        # Create copy
        new_config = dict(pipeline_config)
        ai_config = new_config.get('ai', {})
        if not ai_config:
            return new_config

        runner_config = ai_config.get('runner', {})
        runner_configs = ai_config.get('runner_config', {})

        # Resolve runner ID
        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        if runner_id:
            # Set new format
            runner_config['id'] = runner_id
            # Remove old runner field if present
            if 'runner' in runner_config and is_plugin_runner_id(runner_config['runner']):
                # Already migrated plugin:* format, keep as id
                pass
            elif 'runner' in runner_config:
                # Old built-in runner name, remove after migration
                old_name = runner_config['runner']
                if old_name in OLD_RUNNER_TO_PLUGIN_RUNNER_ID:
                    del runner_config['runner']

            # Migrate runner config
            resolved_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)
            if not resolved_config:
                resolved_config = ConfigMigration.resolve_legacy_runner_config(pipeline_config, runner_id)
            if resolved_config:
                runner_configs[runner_id] = resolved_config
                # Remove old runner config block
                for old_name, mapped_id in OLD_RUNNER_TO_PLUGIN_RUNNER_ID.items():
                    if mapped_id == runner_id and old_name in ai_config:
                        del ai_config[old_name]

        # Update configs
        ai_config['runner'] = runner_config
        ai_config['runner_config'] = runner_configs
        new_config['ai'] = ai_config

        return new_config
