from __future__ import annotations

import time
import typing

from langbot.libs.official_account_api.oaevent import OAEvent
from langbot.pkg.platform.adapters.officialaccount.message_converter import OfficialAccountMessageConverter
from langbot.pkg.platform.adapters.officialaccount.types import ADAPTER_NAME
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class OfficialAccountEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2legacy(self, event: OAEvent) -> platform_events.FriendMessage | None:
        eba_event = await self.target2yiri(event)
        if not isinstance(eba_event, platform_events.MessageReceivedEvent):
            return None
        return platform_events.FriendMessage(
            sender=platform_entities.Friend(
                id=eba_event.sender.id,
                nickname=eba_event.sender.nickname,
                remark='',
            ),
            message_chain=eba_event.message_chain,
            time=eba_event.timestamp,
            source_platform_object=event,
        )

    async def target2yiri(self, event: OAEvent) -> platform_events.Event | None:
        if event.type in {'text', 'image', 'voice'}:
            return await self.message_to_eba(event)
        return self.platform_specific(event, f'officialaccount.{event.detail_type or event.type or "unknown"}')

    async def message_to_eba(self, event: OAEvent) -> platform_events.MessageReceivedEvent:
        sender_id = event.user_id or ''
        timestamp = float(event.timestamp or time.time())
        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.message_id or f'{sender_id}:{int(timestamp)}',
            message_chain=await OfficialAccountMessageConverter.target2yiri(event),
            sender=platform_entities.User(
                id=sender_id,
                nickname=sender_id,
            ),
            chat_type=platform_entities.ChatType.PRIVATE,
            chat_id=sender_id,
            timestamp=timestamp,
            source_platform_object=event,
        )

    @staticmethod
    def platform_specific(event: OAEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=float(event.timestamp or time.time()),
            source_platform_object=event,
        )
