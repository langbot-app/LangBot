"""Claude Code Runner plugin entry point."""

from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class ClaudeCodeAgentPlugin(BasePlugin):
    async def initialize(self) -> None:
        """No tenant configuration is available at process initialization."""
        pass
