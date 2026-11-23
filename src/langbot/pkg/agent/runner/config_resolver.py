"""Resolve the current Runner configuration shape."""

from __future__ import annotations

import typing

from .id import parse_runner_id


HOST_SECURITY_BOOLEAN_FIELDS = (
    'enable-all-tools',
    'mcp-resource-agent-read-enabled',
)


class RunnerConfigResolver:
    """Configuration helpers for the current Runner shape.

    Responsibilities:
    - Resolve runner ID from ai.runner.id
    - Extract Agent/runner config from ai.runner_config
    - Read current conversation expiry settings
    - Validate the persisted 4.x Agent binding container
    """

    @staticmethod
    def validate_agent_config(config: typing.Any) -> dict[str, typing.Any]:
        """Validate and return the persisted 4.x Agent config container."""
        if not isinstance(config, dict):
            raise ValueError('Agent config must be an object')

        runner = config.get('runner')
        if not isinstance(runner, dict):
            raise ValueError("Agent config field 'runner' must be an object")

        runner_id = runner.get('id')
        if not isinstance(runner_id, str):
            raise ValueError("Agent config field 'runner.id' must be a string")

        runner_configs = config.get('runner_config')
        if not isinstance(runner_configs, dict):
            raise ValueError("Agent config field 'runner_config' must be an object")

        for configured_runner_id, runner_config in runner_configs.items():
            if not isinstance(configured_runner_id, str) or not configured_runner_id:
                raise ValueError("Agent config field 'runner_config' must use non-empty string runner IDs")
            if not isinstance(runner_config, dict):
                raise ValueError(f'Agent runner_config[{configured_runner_id!r}] must be an object')

        if runner_id and runner_id not in runner_configs:
            raise ValueError(f'Agent runner_config is missing selected runner {runner_id!r}')

        if runner_id:
            RunnerConfigResolver.validate_runner_security_fields(
                runner_configs[runner_id],
                context=f'Agent runner_config[{runner_id!r}]',
            )

        return config

    @staticmethod
    def validate_runner_security_fields(
        runner_config: dict[str, typing.Any],
        *,
        context: str = 'Runner config',
    ) -> dict[str, typing.Any]:
        """Reject malformed Host-owned security toggles instead of enabling them."""
        for field_name in HOST_SECURITY_BOOLEAN_FIELDS:
            if field_name in runner_config and not isinstance(runner_config[field_name], bool):
                raise ValueError(f'{context} field {field_name!r} must be a boolean')

        RunnerConfigResolver.validate_mcp_resource_attachments(
            runner_config.get('mcp-resources'),
            context=context,
            field_name='mcp-resources',
        )
        return runner_config

    @staticmethod
    def validate_mcp_resource_attachments(
        resources: typing.Any,
        *,
        context: str,
        field_name: str,
    ) -> typing.Any:
        """Validate explicit attachment enable flags shared by Agent and Pipeline inputs."""
        if not isinstance(resources, list):
            return resources
        for index, resource in enumerate(resources):
            if not isinstance(resource, dict) or 'enabled' not in resource:
                continue
            if not isinstance(resource['enabled'], bool):
                raise ValueError(f"{context} field '{field_name}[{index}].enabled' must be a boolean")
        return resources

    @classmethod
    def validate_pipeline_config(cls, config: typing.Any) -> dict[str, typing.Any]:
        """Validate the selected Runner container in a current 4.x Pipeline config."""
        if not isinstance(config, dict):
            raise ValueError('Pipeline config must be an object')

        ai_config = config.get('ai')
        if ai_config is None:
            return config
        if not isinstance(ai_config, dict):
            raise ValueError("Pipeline config field 'ai' must be an object")

        runner = ai_config.get('runner')
        if runner is None:
            return config
        if not isinstance(runner, dict):
            raise ValueError("Pipeline config field 'ai.runner' must be an object")

        runner_id = runner.get('id')
        if not isinstance(runner_id, str):
            raise ValueError("Pipeline config field 'ai.runner.id' must be a string")
        if not runner_id:
            return config
        cls.validate_runner_id(runner_id)

        runner_configs = ai_config.get('runner_config')
        if not isinstance(runner_configs, dict):
            raise ValueError("Pipeline config field 'ai.runner_config' must be an object")
        if runner_id not in runner_configs:
            raise ValueError(f'Pipeline runner_config is missing selected runner {runner_id!r}')

        selected_config = runner_configs[runner_id]
        if not isinstance(selected_config, dict):
            raise ValueError(f'Pipeline runner_config[{runner_id!r}] must be an object')
        cls.validate_runner_security_fields(
            selected_config,
            context=f'Pipeline runner_config[{runner_id!r}]',
        )
        return config

    @staticmethod
    def resolve_agent_id(config: dict[str, typing.Any]) -> str | None:
        """Resolve a runner ID from a validated persisted Agent config."""
        runner = config.get('runner', {})
        runner_id = runner.get('id') if isinstance(runner, dict) else None
        return runner_id if isinstance(runner_id, str) and runner_id else None

    @classmethod
    def resolve_agent_config(
        cls,
        config: typing.Any,
    ) -> tuple[dict[str, typing.Any], str | None, dict[str, typing.Any]]:
        """Validate an Agent config and return its selected runner configuration."""
        validated = cls.validate_agent_config(config)
        runner_id = cls.resolve_agent_id(validated)
        runner_configs = typing.cast(dict[str, typing.Any], validated['runner_config'])
        runner_config = runner_configs.get(runner_id, {}) if runner_id else {}
        return validated, runner_id, typing.cast(dict[str, typing.Any], runner_config)

    @staticmethod
    def legacy_runner_target(runner_id: str) -> str | None:
        """The plugin Runner ID that replaced a pre-4.11 built-in runner name."""
        from ...pipeline.legacy_config_migration import _TARGETS

        target = _TARGETS.get(runner_id)
        return f'plugin:langbot-team/{target[0]}/default' if target else None

    @classmethod
    def validate_runner_id(cls, runner_id: str) -> None:
        """Reject a selected Runner ID that no Runner can ever have."""
        try:
            parse_runner_id(runner_id)
        except ValueError as exc:
            target = cls.legacy_runner_target(runner_id)
            if target:
                raise ValueError(
                    f"Pipeline config field 'ai.runner.id' uses the pre-4.11 runner name {runner_id!r}; "
                    f'select {target!r} instead or migrate the pipeline with the pipeline migration assistant'
                ) from exc
            raise ValueError(
                f"Pipeline config field 'ai.runner.id' must be a plugin Runner ID "
                f"('plugin:<author>/<plugin>/<runner>'), got {runner_id!r}"
            ) from exc

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
