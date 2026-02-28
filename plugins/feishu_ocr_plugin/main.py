from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class FeishuOcrPlugin(BasePlugin):
    async def initialize(self) -> None:
        # Called when plugin process starts.
        pass

    def __del__(self) -> None:
        # Called when plugin process exits.
        pass
