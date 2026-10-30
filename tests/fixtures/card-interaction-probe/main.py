"""A local test plugin for event-processor card interactions."""

from langbot_plugin.api.definition.plugin import BasePlugin


class CardInteractionProbePlugin(BasePlugin):
    async def initialize(self) -> None:
        pass
