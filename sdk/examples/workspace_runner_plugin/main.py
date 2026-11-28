from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class WorkspaceRunnerPlugin(BasePlugin):
    """Entry point for the workspace runner example plugin."""

    async def initialize(self) -> None:
        return None
