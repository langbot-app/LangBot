"""Installation permissions declared by a Plugin manifest."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Capability = Literal[
    "langbot.info",
    "bot.read",
    "bot.message.send",
    "bot.platform_api",
    "models.read",
    "models.invoke",
    "storage.plugin",
    "storage.workspace",
    "knowledge.read",
    "knowledge.vector",
    "knowledge.parser",
    "config.read",
    "plugin_tools",
    "mcp",
    "sandbox",
    "plugin.read",
]


class PluginPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    workspace_operations: list[str] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
