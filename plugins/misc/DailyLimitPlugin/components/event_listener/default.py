from __future__ import annotations

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DefaultEventListener(EventListener):
    """Counts conversations per session and blocks when the daily limit is hit."""

    async def initialize(self):
        await super().initialize()

        @self.handler(events.PersonNormalMessageReceived)
        async def on_person_message(event_context: context.EventContext):
            await self._check(event_context, "person")

        @self.handler(events.GroupNormalMessageReceived)
        async def on_group_message(event_context: context.EventContext):
            await self._check(event_context, "group")

    async def _check(self, event_context: context.EventContext, launcher_type: str):
        event = event_context.event
        # Session identity: a conversation = launcher_type + launcher_id
        # (a private chat or a specific group), matching how LangBot scopes
        # conversations. sender_id is kept in the label for group visibility.
        session_id = f"{launcher_type}:{event.launcher_id}"
        label = session_id
        if launcher_type == "group" and str(event.sender_id) != str(event.launcher_id):
            label = f"{session_id} (user {event.sender_id})"

        allowed, message = await self.plugin.check_and_count(session_id, label)
        if allowed:
            return

        if message:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=message),
                ])
            )
        event_context.prevent_default()
        event_context.prevent_postorder()
