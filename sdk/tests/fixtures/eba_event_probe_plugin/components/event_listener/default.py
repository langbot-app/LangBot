from __future__ import annotations

import json
import os
from pathlib import Path

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events


class EBAEventProbeListener(EventListener):
    def __init__(self):
        super().__init__()
        self.log_path = Path(os.getenv("EBA_PROBE_LOG", "eba_event_probe.jsonl"))

        for event_type in (
            events.MessageReceived,
            events.MessageEdited,
            events.MessageReactionReceived,
            events.FeedbackReceived,
            events.GroupMemberJoined,
            events.GroupMemberLeft,
            events.GroupMemberBanned,
            events.BotInvitedToGroup,
            events.BotRemovedFromGroup,
            events.BotMuted,
            events.BotUnmuted,
            events.PlatformSpecificEventReceived,
        ):
            self.handler(event_type)(self._record)

    async def _record(self, event_context: context.EventContext):
        event_data = event_context.event.model_dump()
        record = {
            "event_name": event_context.event_name,
            "query_id": event_context.query_id,
            "event": event_data,
        }
        with self.log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"EBA_PROBE_EVENT {event_context.event_name}")
