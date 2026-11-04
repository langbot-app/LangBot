from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events


class BridgeListener(EventListener):
    async def initialize(self):
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def on_person(event_context):
            await self.plugin.handle_person(event_context)

        @self.handler(events.GroupMessageReceived)
        async def on_group(event_context):
            await self.plugin.handle_group(event_context)
