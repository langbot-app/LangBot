import logging

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events

from main import permission_denied

logger = logging.getLogger(__name__)


class LeadListener(EventListener):
    async def initialize(self):
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def on_person(event_context):
            await self.guard(self.plugin.on_person_message(event_context))

        @self.handler(events.NormalMessageResponded)
        async def on_responded(event_context):
            await self.guard(self.plugin.on_responded(event_context))

    @staticmethod
    async def guard(call):
        """Never let lead capture break the conversation."""
        try:
            await call
        except Exception as error:
            if permission_denied(error):
                logger.warning("LeadCapture is missing a permission; confirm it on the plugin page.")
                return
            logger.exception("LeadCapture failed")
