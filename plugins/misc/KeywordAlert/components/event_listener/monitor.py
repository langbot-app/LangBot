from __future__ import annotations

import logging
import traceback

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message

logger = logging.getLogger("KeywordAlert.monitor")


class KeywordMonitor(EventListener):
    """Monitors group messages for configured keywords."""

    def __init__(self):
        super().__init__()

        @self.handler(events.GroupMessageReceived)
        async def on_group_message(event_context: context.EventContext):
            await self._handle(event_context)

    async def _handle(self, event_context: context.EventContext):
        try:
            plugin = self.plugin
            event = event_context.event

            group_id = str(event.launcher_id)
            sender_id = str(event.sender_id)

            # Check if this group is monitored
            allowed_groups = plugin.parse_group_ids()
            if allowed_groups is not None and group_id not in allowed_groups:
                return

            # Extract text
            text_parts = []
            for component in event.message_chain:
                if isinstance(component, platform_message.Plain):
                    text_parts.append(component.text)
            text = "".join(text_parts).strip()
            if not text:
                return

            # Check keywords
            keywords = plugin.parse_keywords()
            if not keywords:
                return

            config = plugin.get_config()
            case_sensitive = config.get("case_sensitive", False)
            match_text = text if case_sensitive else text.lower()

            for keyword in keywords:
                match_keyword = keyword if case_sensitive else keyword.lower()
                if match_keyword in match_text:
                    if plugin.check_cooldown(group_id, keyword):
                        await plugin.send_alert(group_id, sender_id, keyword, text)
                    break  # One alert per message

        except Exception as e:
            logger.error(f"Error in keyword monitor: {e}\n{traceback.format_exc()}")
