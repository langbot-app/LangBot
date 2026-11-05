import logging

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events

from main import permission_denied, permission_notice


class BridgeListener(EventListener):
    async def initialize(self):
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def on_person(event_context):
            try:
                await self.plugin.handle_person(event_context)
            except Exception as error:
                if not permission_denied(error):
                    raise
                event_context.prevent_default()
                event_context.prevent_postorder()
                logging.getLogger(__name__).warning(
                    permission_notice("storage.plugin / bot.message.send")
                )
