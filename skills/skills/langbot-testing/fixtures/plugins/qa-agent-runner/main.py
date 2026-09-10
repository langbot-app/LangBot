from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class QARunnerPlugin(BasePlugin):
    async def initialize(self) -> None:
        self.ready_marker = 'qa-agent-runner-ready'
