"""Agent runner descriptor."""

from __future__ import annotations

import typing
import pydantic

from langbot_plugin.api.entities.builtin.runner.manifest import (
    RunnerCapabilities,
    RunnerPermissions,
)


class RunnerDescriptor(pydantic.BaseModel):
    """Descriptor for an agent runner.

    Represents the discovered metadata for a runner, including
    its identity, capabilities, permissions, and configuration schema.
    """

    id: str
    """Unique runner ID: plugin:author/plugin_name/runner_name"""

    source: typing.Literal['plugin']
    """Runner source type"""

    label: dict[str, str]
    """Display labels keyed by locale (e.g., en_US, zh_Hans)"""

    description: dict[str, str] | None = None
    """Optional description keyed by locale"""

    plugin_author: str
    """Plugin author from manifest"""

    plugin_name: str
    """Plugin name from manifest"""

    runner_name: str
    """Runner component name from manifest"""

    plugin_version: str | None = None
    """Optional plugin version"""

    config_schema: list[dict[str, typing.Any]] = pydantic.Field(default_factory=list)
    """Configuration schema using DynamicForm format"""

    capabilities: RunnerCapabilities = pydantic.Field(default_factory=RunnerCapabilities)
    """Runner capabilities: streaming, tool_calling, knowledge_retrieval, etc."""

    permissions: RunnerPermissions | dict[str, typing.Any] = pydantic.Field(default_factory=RunnerPermissions)
    """Requested LangBot resource permissions."""

    raw_manifest: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Original manifest for reference"""

    component_kind: typing.Literal['Runner'] = 'Runner'
    usages: list[typing.Literal['agent', 'event']] = pydantic.Field(min_length=1)
    supported_event_patterns: list[str] = pydantic.Field(default_factory=lambda: ['*'])

    model_config = pydantic.ConfigDict(
        extra='allow',
    )

    def get_plugin_id(self) -> str:
        """Return plugin identifier as author/name."""
        return f'{self.plugin_author}/{self.plugin_name}'

    def supports_streaming(self) -> bool:
        """Check if runner supports streaming output."""
        return self.capabilities.streaming

    def supports_tool_calling(self) -> bool:
        """Check if runner supports tool calling."""
        return self.capabilities.tool_calling

    def supports_knowledge_retrieval(self) -> bool:
        """Check if runner supports knowledge retrieval."""
        return self.capabilities.knowledge_retrieval

    def supports_steering(self) -> bool:
        """Check if runner supports run steering/follow-up input."""
        return bool(getattr(self.capabilities, 'steering', False))

    def declared_workspace_operations(self) -> list[str]:
        """Return list of workspace operations declared in runner manifest permissions.

        Uses getattr for compatibility with SDK 0.7.19 where workspace_operations does not exist.
        In SDK 0.7.19 environment, this returns empty list so the feature is disabled safely.
        """
        permissions = getattr(self, 'permissions', None)
        if isinstance(permissions, dict):
            return list(permissions.get('workspace_operations') or [])
        return list(getattr(permissions, 'workspace_operations', []) or [])

    @property
    def workspace_operations(self) -> list[str]:
        """Declared workspace operations from manifest."""
        return self.declared_workspace_operations()


def is_local_agent(descriptor: RunnerDescriptor | None) -> bool:
    """Check if descriptor represents LocalAgent."""
    if descriptor is None:
        return False
    runner_id = getattr(descriptor, 'id', '')
    if runner_id == 'defaultrunner' or runner_id == 'plugin:langbot-team/LocalAgent/default':
        return True
    return (
        getattr(descriptor, 'plugin_author', None) == 'langbot-team'
        and getattr(descriptor, 'plugin_name', None) == 'LocalAgent'
    )


def resolve_authorized_workspace_operations(
    descriptor: RunnerDescriptor | None,
    configured_operations: typing.Iterable[str] | None,
) -> list[str]:
    """Calculate effective authorized workspace operations at runtime.

    LocalAgent is not constrained by manifest; it receives all operations
    configured by the user.
    Plugin runners are restricted to the intersection of configured operations and
    operations declared in the runner's manifest permissions.
    """
    configured = [str(op) for op in (configured_operations or [])]
    if is_local_agent(descriptor):
        return configured
    declared = set(descriptor.declared_workspace_operations() if descriptor is not None else [])
    return [op for op in configured if op in declared]
