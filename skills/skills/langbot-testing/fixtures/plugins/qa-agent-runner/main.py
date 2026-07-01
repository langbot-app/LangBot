from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class QAAgentRunnerPlugin(BasePlugin):
    async def initialize(self) -> None:
        self.ready_marker = "qa-agent-runner-ready"
