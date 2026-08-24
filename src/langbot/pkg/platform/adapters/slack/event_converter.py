from __future__ import annotations

import time
import typing

from langbot.libs.slack_api.slackevent import SlackEvent
from langbot.pkg.platform.adapters.slack.message_converter import SlackMessageConverter
from langbot.pkg.platform.adapters.slack.types import ADAPTER_NAME
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class SlackEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self, bot_token: str = ''):
        self.bot_token = bot_token

    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2legacy(self, event: SlackEvent) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
        eba_event = await self.target2yiri(event)
        if not isinstance(eba_event, platform_events.MessageReceivedEvent):
            return None
        if eba_event.chat_type == platform_entities.ChatType.PRIVATE:
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
        return platform_events.GroupMessage(
            sender=platform_entities.GroupMember(
                id=eba_event.sender.id,
                member_name=eba_event.sender.nickname,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=eba_event.group.id if eba_event.group else eba_event.chat_id,
                    name=eba_event.group.name if eba_event.group else '',
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
            ),
            message_chain=eba_event.message_chain,
            time=eba_event.timestamp,
            source_platform_object=event,
        )

    async def target2yiri(self, event: SlackEvent) -> platform_events.Event:
        if event.type in {'im', 'channel'}:
            return await self.message_to_eba(event)
        return self.platform_specific(event, f'slack.{event.type or "unknown"}')

    async def message_to_eba(self, event: SlackEvent) -> platform_events.MessageReceivedEvent:
        sender_id = event.user_id or ''
        sender = platform_entities.User(
            id=sender_id,
            nickname=event.sender_name or sender_id,
        )
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = sender_id
        group = None
        if event.type == 'channel':
            chat_type = platform_entities.ChatType.GROUP
            chat_id = event.channel_id or ''
            group = platform_entities.UserGroup(id=str(chat_id), name=str(chat_id))

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.message_id or event.get('event', {}).get('event_ts') or '',
            message_chain=await SlackMessageConverter.target2yiri(event, self.bot_token),
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id or '',
            group=group,
            timestamp=_timestamp_value(event),
            source_platform_object=event,
        )

    @staticmethod
    def platform_specific(event: SlackEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=_timestamp_value(event),
            source_platform_object=event,
        )


def _timestamp_value(event: SlackEvent) -> float:
    raw_ts = event.get('event', {}).get('ts') or event.get('event', {}).get('event_ts')
    try:
        return float(raw_ts)
    except (TypeError, ValueError):
        return time.time()
