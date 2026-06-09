"""Agent runner descriptor."""
from __future__ import annotations

import typing
import pydantic


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

    config_schema: list[dict[str, typing.Any]] = []
    """Configuration schema using DynamicForm format"""

    capabilities: dict[str, bool] = {}
    """Runner capabilities: streaming, tool_calling, knowledge_retrieval, etc."""

    permissions: dict[str, list[str]] = {}
    """Requested permissions: models, tools, knowledge_bases, storage, files, platform_api"""

    raw_manifest: dict[str, typing.Any] = {}
    """Original manifest for reference"""

    model_config = pydantic.ConfigDict(
        extra='allow',
    )

    def get_plugin_id(self) -> str:
        """Return plugin identifier as author/name."""
        return f'{self.plugin_author}/{self.plugin_name}'

    def supports_streaming(self) -> bool:
        """Check if runner supports streaming output."""
        return self.capabilities.get('streaming', False)

    def supports_tool_calling(self) -> bool:
        """Check if runner supports tool calling."""
        return self.capabilities.get('tool_calling', False)

    def supports_knowledge_retrieval(self) -> bool:
        """Check if runner supports knowledge retrieval."""
        return self.capabilities.get('knowledge_retrieval', False)
