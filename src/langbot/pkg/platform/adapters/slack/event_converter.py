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
    def __init__(self, bot_token: str = '', bot_user_id: str = ''):
        self.bot_token = bot_token
        self.bot_user_id = bot_user_id
        self.private_chats: dict[str, str] = {}

    def remember_private_chat(self, channel_id: str, user_id: str):
        if channel_id and user_id:
            self.private_chats[channel_id] = user_id
            while len(self.private_chats) > 4096:
                self.private_chats.pop(next(iter(self.private_chats)))

    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2legacy(
        self, event: SlackEvent
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

    async def target2yiri(self, event: SlackEvent) -> platform_events.Event:
        raw = event.get('event', {})
        kind = raw.get('type', '')
        subtype = raw.get('subtype', '')
        common = dict(
            adapter_name=ADAPTER_NAME,
            timestamp=_timestamp_value(event),
            source_platform_object=SlackEvent(_public_payload(dict(event))),
        )
        channel = raw.get('channel', '') or raw.get('item', {}).get('channel', '')
        channel_info = channel if isinstance(channel, dict) else {'id': channel}
        channel_id = channel_info.get('id', '')
        group = platform_entities.UserGroup(id=channel_id, name=channel_info.get('name', channel_id))

        def user(uid):
            return platform_entities.User(id=uid, nickname=uid) if uid else None

        private = raw.get('channel_type') == 'im' or str(channel_id).startswith('D')
        chat = dict(
            chat_type=platform_entities.ChatType.PRIVATE if private else platform_entities.ChatType.GROUP,
            chat_id=self.private_chats.get(channel_id, channel_id) if private else channel_id,
            group=None if private else group,
        )
        if kind == 'message' and subtype == 'message_changed':
            message = raw.get('message', {})
            updated = SlackEvent({**event, 'event': {**raw, **message}})
            return platform_events.MessageEditedEvent(
                **common,
                **chat,
                message_id=message.get('ts', ''),
                editor=user(message.get('edited', {}).get('user') or message.get('user')) or user('unknown'),
                new_content=await SlackMessageConverter.target2yiri(updated, self.bot_token),
            )
        if kind == 'message' and subtype == 'message_deleted':
            return platform_events.MessageDeletedEvent(**common, **chat, message_id=raw.get('deleted_ts', ''))
        if kind in {'reaction_added', 'reaction_removed'} and raw.get('item', {}).get('type') == 'message':
            return platform_events.MessageReactionEvent(
                **common,
                **chat,
                message_id=raw['item'].get('ts', ''),
                user=user(raw.get('user')) or user('unknown'),
                reaction=raw.get('reaction', ''),
                is_add=kind == 'reaction_added',
            )
        if kind in {'member_joined_channel', 'member_left_channel'}:
            member = user(raw.get('user')) or user('unknown')
            inviter = user(raw.get('inviter'))
            if self.bot_user_id and raw.get('user') == self.bot_user_id:
                if kind == 'member_joined_channel' and inviter:
                    return platform_events.BotInvitedToGroupEvent(**common, group=group, inviter=inviter)
                if kind == 'member_left_channel':
                    return platform_events.BotRemovedFromGroupEvent(**common, group=group)
            if kind == 'member_joined_channel':
                return platform_events.MemberJoinedEvent(
                    **common,
                    group=group,
                    member=member,
                    inviter=inviter,
                    join_type='invite' if inviter else 'direct',
                )
            return platform_events.MemberLeftEvent(**common, group=group, member=member)
        fields = {
            'channel_rename': 'name',
            'group_rename': 'name',
            'channel_archive': 'archived',
            'channel_unarchive': 'archived',
            'group_archive': 'archived',
            'group_unarchive': 'archived',
            'channel_topic': 'topic',
            'group_topic': 'topic',
            'channel_purpose': 'purpose',
            'group_purpose': 'purpose',
        }
        change = subtype if kind == 'message' else kind
        if change in fields:
            return platform_events.GroupInfoUpdatedEvent(
                **common,
                group=group,
                operator=user(raw.get('user')),
                changed_fields=[fields[change]],
            )
        if (
            kind in {'message', 'app_mention'}
            and subtype in {'', 'file_share', 'thread_broadcast'}
            and event.type in {'im', 'channel'}
        ):
            return await self.message_to_eba(event)
        return self.platform_specific(event, f'slack.{subtype or kind or event.get("type") or event.type or "unknown"}')

    async def message_to_eba(self, event: SlackEvent) -> platform_events.MessageReceivedEvent:
        sender_id = event.user_id or ''
        sender = platform_entities.User(
            id=sender_id,
            nickname=event.sender_name or sender_id,
        )
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = sender_id
        group = None
        if event.type == 'im':
            self.remember_private_chat(event.channel_id, sender_id)
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
            source_platform_object=SlackEvent(_public_payload(dict(event))),
        )

    @staticmethod
    def platform_specific(event: SlackEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=_public_payload(dict(event)),
            timestamp=_timestamp_value(event),
            source_platform_object=SlackEvent(_public_payload(dict(event))),
        )


def _timestamp_value(event: SlackEvent) -> float:
    raw_ts = event.get('event', {}).get('event_ts') or event.get('event', {}).get('ts') or event.get('event_time')
    try:
        return float(raw_ts)
    except (TypeError, ValueError):
        return time.time()


def _public_payload(value):
    """Keep callback credentials out of event data and monitoring records."""
    if isinstance(value, dict):
        return {
            key: _public_payload(item)
            for key, item in value.items()
            if key not in {'token', 'response_url', 'response_urls'}
        }
    if isinstance(value, list):
        return [_public_payload(item) for item in value]
    return value
