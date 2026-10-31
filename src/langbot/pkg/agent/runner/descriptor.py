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

    permissions: RunnerPermissions = pydantic.Field(default_factory=RunnerPermissions)
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
