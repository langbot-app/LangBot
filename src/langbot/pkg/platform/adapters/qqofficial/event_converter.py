from __future__ import annotations

import datetime
import time
import typing

from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from langbot.pkg.platform.adapters.qqofficial.message_converter import QQOfficialMessageConverter
from langbot.pkg.platform.adapters.qqofficial.types import ADAPTER_NAME
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class QQOfficialEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2legacy(self, event: QQOfficialEvent) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
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

    async def target2yiri(self, event: QQOfficialEvent) -> platform_events.Event:
        if event.t in {'C2C_MESSAGE_CREATE', 'DIRECT_MESSAGE_CREATE', 'GROUP_AT_MESSAGE_CREATE', 'AT_MESSAGE_CREATE'}:
            return await self.message_to_eba(event)
        return self.platform_specific(event, f'qqofficial.{event.t or "unknown"}')

    async def message_to_eba(self, event: QQOfficialEvent) -> platform_events.MessageReceivedEvent:
        timestamp = _timestamp_value(event.timestamp)
        sender = platform_entities.User(
            id=self._sender_id(event),
            nickname=event.username or self._sender_id(event),
        )
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = self._private_chat_id(event)
        group = None
        if event.t in {'GROUP_AT_MESSAGE_CREATE', 'AT_MESSAGE_CREATE'}:
            chat_type = platform_entities.ChatType.GROUP
            chat_id = event.channel_id if event.t == 'AT_MESSAGE_CREATE' else event.group_openid
            chat_id = chat_id or event.group_openid or event.channel_id or ''
            group = platform_entities.UserGroup(id=str(chat_id), name=str(chat_id))

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.d_id or event.id or '',
            message_chain=await QQOfficialMessageConverter.target2yiri(event),
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id or '',
            group=group,
            timestamp=timestamp,
            source_platform_object=event,
        )

    @staticmethod
    def _sender_id(event: QQOfficialEvent) -> str:
        member_openid = event.member_openid or event.get('member_openid', '')
        if event.t in {'GROUP_AT_MESSAGE_CREATE', 'AT_MESSAGE_CREATE'}:
            return member_openid or event.user_openid or event.d_author_id or ''
        return event.user_openid or member_openid or event.d_author_id or event.guild_id or event.group_openid or ''

    @staticmethod
    def _private_chat_id(event: QQOfficialEvent) -> str:
        if event.t == 'DIRECT_MESSAGE_CREATE':
            return event.guild_id or event.user_openid or ''
        return event.user_openid or event.guild_id or ''

    @staticmethod
    def platform_specific(event: QQOfficialEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=_timestamp_value(event.timestamp),
            source_platform_object=event,
        )


def _timestamp_value(value: str) -> float:
    if not value:
        return time.time()
    try:
        return float(datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z').timestamp())
    except (TypeError, ValueError):
        return time.time()
