"""Agent runner descriptor."""
from __future__ import annotations

import typing
import pydantic

from langbot_plugin.api.entities.builtin.agent_runner.manifest import (
    AgentRunnerCapabilities,
    AgentRunnerPermissions,
)


class AgentRunnerDescriptor(pydantic.BaseModel):
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
    """AgentRunner component name from manifest"""

    plugin_version: str | None = None
    """Optional plugin version"""

    config_schema: list[dict[str, typing.Any]] = pydantic.Field(default_factory=list)
    """Configuration schema using DynamicForm format"""

    capabilities: AgentRunnerCapabilities = pydantic.Field(
        default_factory=AgentRunnerCapabilities
    )
    """Runner capabilities: streaming, tool_calling, knowledge_retrieval, etc."""

    permissions: AgentRunnerPermissions = pydantic.Field(
        default_factory=AgentRunnerPermissions
    )
    """Requested LangBot resource permissions."""

    raw_manifest: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Original manifest for reference"""

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
