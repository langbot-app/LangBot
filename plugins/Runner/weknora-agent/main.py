"""WeKnora Agent plugin entry point."""

from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class WeKnoraAgentPlugin(BasePlugin):
    """WeKnora Agent plugin."""

    def __init__(self):
        super().__init__()

    async def initialize(self) -> None:
        """Initialize the plugin."""
        pass
