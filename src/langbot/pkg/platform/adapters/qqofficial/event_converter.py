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


MESSAGE_EVENT_TYPES = {
    'C2C_MESSAGE_CREATE',
    'DIRECT_MESSAGE_CREATE',
    'GROUP_AT_MESSAGE_CREATE',
    'AT_MESSAGE_CREATE',
}
REACTION_ADD_EVENT_TYPES = {'MESSAGE_REACTION_ADD'}
REACTION_REMOVE_EVENT_TYPES = {'MESSAGE_REACTION_REMOVE'}
MEMBER_JOINED_EVENT_TYPES = {'GUILD_MEMBER_ADD', 'GROUP_MEMBER_ADD'}
MEMBER_LEFT_EVENT_TYPES = {'GUILD_MEMBER_REMOVE', 'GROUP_MEMBER_REMOVE'}
BOT_INVITED_EVENT_TYPES = {'GUILD_CREATE', 'GROUP_ADD_ROBOT'}
BOT_REMOVED_EVENT_TYPES = {'GUILD_DELETE', 'GROUP_DEL_ROBOT'}


class QQOfficialEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2legacy(
        self, event: QQOfficialEvent
    ) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
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
        if event.t in MESSAGE_EVENT_TYPES:
            return await self.message_to_eba(event)
        if event.t in REACTION_ADD_EVENT_TYPES | REACTION_REMOVE_EVENT_TYPES:
            return self.reaction_to_eba(event, event.t in REACTION_ADD_EVENT_TYPES)
        if event.t in MEMBER_JOINED_EVENT_TYPES:
            return self.member_joined_to_eba(event)
        if event.t in MEMBER_LEFT_EVENT_TYPES:
            return self.member_left_to_eba(event)
        if event.t in BOT_INVITED_EVENT_TYPES:
            return self.bot_invited_to_eba(event)
        if event.t in BOT_REMOVED_EVENT_TYPES:
            return self.bot_removed_to_eba(event)
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

    def reaction_to_eba(self, event: QQOfficialEvent, is_add: bool) -> platform_events.MessageReactionEvent:
        chat_type, chat_id, group = self._chat_from_event(event)
        return platform_events.MessageReactionEvent(
            type='message.reaction',
            adapter_name=ADAPTER_NAME,
            message_id=_event_value(event, 'message_id', 'msg_id', 'target_id', 'id'),
            user=platform_entities.User(
                id=_event_value(event, 'user_openid', 'member_openid', 'openid', 'user_id'),
                nickname=_event_value(event, 'username', 'nick', 'nickname', 'user_openid', 'openid'),
            ),
            reaction=_event_value(event, 'emoji', 'emoji_id', 'reaction', 'reaction_id', 'type'),
            is_add=is_add,
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
            timestamp=_timestamp_value(event.timestamp),
            source_platform_object=event,
        )

    def member_joined_to_eba(self, event: QQOfficialEvent) -> platform_events.MemberJoinedEvent:
        group = self._group_from_event(event)
        member = self._user_from_event(event, 'openid', 'member_openid', 'user_openid', 'user_id')
        inviter_id = _event_value(event, 'inviter_openid', 'operator_openid', 'op_user_id')
        return platform_events.MemberJoinedEvent(
            type='group.member_joined',
            adapter_name=ADAPTER_NAME,
            group=group,
            member=member,
            inviter=platform_entities.User(id=inviter_id, nickname=inviter_id) if inviter_id else None,
            timestamp=_timestamp_value(event.timestamp),
            source_platform_object=event,
        )

    def member_left_to_eba(self, event: QQOfficialEvent) -> platform_events.MemberLeftEvent:
        group = self._group_from_event(event)
        member = self._user_from_event(event, 'openid', 'member_openid', 'user_openid', 'user_id')
        operator_id = _event_value(event, 'operator_openid', 'op_user_id', 'user_openid')
        return platform_events.MemberLeftEvent(
            type='group.member_left',
            adapter_name=ADAPTER_NAME,
            group=group,
            member=member,
            operator=platform_entities.User(id=operator_id, nickname=operator_id) if operator_id else None,
            is_kicked=event.t in {'GROUP_MEMBER_REMOVE', 'GUILD_MEMBER_REMOVE'},
            timestamp=_timestamp_value(event.timestamp),
            source_platform_object=event,
        )

    def bot_invited_to_eba(self, event: QQOfficialEvent) -> platform_events.BotInvitedToGroupEvent:
        group = self._group_from_event(event)
        inviter_id = _event_value(event, 'op_user_id', 'operator_openid', 'user_openid', 'member_openid', 'openid')
        return platform_events.BotInvitedToGroupEvent(
            type='bot.invited_to_group',
            adapter_name=ADAPTER_NAME,
            group=group,
            inviter=platform_entities.User(id=inviter_id, nickname=inviter_id) if inviter_id else None,
            request_id=_event_value(event, 'event_id', 'id'),
            timestamp=_timestamp_value(event.timestamp),
            source_platform_object=event,
        )

    def bot_removed_to_eba(self, event: QQOfficialEvent) -> platform_events.BotRemovedFromGroupEvent:
        group = self._group_from_event(event)
        operator_id = _event_value(event, 'op_user_id', 'operator_openid', 'user_openid', 'member_openid', 'openid')
        return platform_events.BotRemovedFromGroupEvent(
            type='bot.removed_from_group',
            adapter_name=ADAPTER_NAME,
            group=group,
            operator=platform_entities.User(id=operator_id, nickname=operator_id) if operator_id else None,
            timestamp=_timestamp_value(event.timestamp),
            source_platform_object=event,
        )

    def _chat_from_event(
        self, event: QQOfficialEvent
    ) -> tuple[platform_entities.ChatType, str, platform_entities.UserGroup | None]:
        group_id = _event_value(event, 'group_openid', 'guild_id', 'channel_id', 'group_id')
        if group_id:
            return platform_entities.ChatType.GROUP, group_id, self._group_from_event(event)
        private_id = _event_value(event, 'user_openid', 'member_openid', 'openid', 'user_id')
        return platform_entities.ChatType.PRIVATE, private_id, None

    @staticmethod
    def _group_from_event(event: QQOfficialEvent) -> platform_entities.UserGroup:
        group_id = _event_value(event, 'group_openid', 'guild_id', 'channel_id', 'group_id')
        group_name = _event_value(event, 'group_name', 'guild_name', 'channel_name', 'name') or group_id
        return platform_entities.UserGroup(id=group_id, name=group_name)

    @staticmethod
    def _user_from_event(event: QQOfficialEvent, *keys: str) -> platform_entities.User:
        user_id = _event_value(event, *keys)
        nickname = _event_value(event, 'username', 'nick', 'nickname') or user_id
        return platform_entities.User(id=user_id, nickname=nickname)

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


def _event_value(event: QQOfficialEvent, *keys: str) -> str:
    nested = event.get('d') if isinstance(event.get('d'), dict) else {}
    for key in keys:
        value = event.get(key)
        if value in (None, '', {}):
            value = nested.get(key)
        if value not in (None, '', {}):
            return str(value)
    return ''


def _timestamp_value(value: str) -> float:
    if not value:
        return time.time()
    try:
        return float(datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z').timestamp())
    except (TypeError, ValueError):
        return time.time()
