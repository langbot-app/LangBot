from __future__ import annotations

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class MessageCollector(EventListener):
    """Listens to all group messages and records them for summarization."""

    def __init__(self):
        super().__init__()

        @self.handler(events.GroupMessageReceived)
        async def on_group_message(event_context: context.EventContext):
            """Capture every group message into the buffer."""
            event = event_context.event

            # Extract plain text from message chain
            text_parts = []
            for component in event.message_chain:
                if isinstance(component, platform_message.Plain):
                    text_parts.append(component.text)

            text = "".join(text_parts).strip()
            if not text:
                return

            # Get sender name from message event if available
            sender_name = str(event.sender_id)
            if hasattr(event.message_event, "sender"):
                sender = event.message_event.sender
                if hasattr(sender, "member_name") and sender.member_name:
                    sender_name = sender.member_name
                elif hasattr(sender, "nickname") and sender.nickname:
                    sender_name = sender.nickname

            # Get bot_uuid for auto-summary
            bot_uuid = None
            if hasattr(event, "query") and event.query:
                if hasattr(event.query, "bot_uuid"):
                    bot_uuid = event.query.bot_uuid

            await self.plugin.record_message(
                launcher_type=event.launcher_type,
                launcher_id=event.launcher_id,
                sender_id=event.sender_id,
                sender_name=sender_name,
                text=text,
                bot_uuid=bot_uuid,
            )
