from __future__ import annotations

import typing

from linebot.v3.webhooks import (
    BeaconEvent,
    Event,
    FollowEvent,
    GroupSource,
    JoinEvent,
    LeaveEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MessageEvent,
    PostbackEvent,
    RoomSource,
    UnfollowEvent,
    UnsendEvent,
    UserSource,
)

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events

from langbot.pkg.platform.adapters.line.message_converter import LineMessageConverter
from langbot.pkg.platform.adapters.line.types import ADAPTER_NAME


def _timestamp(event: Event) -> float:
    try:
        return float(event.timestamp) / 1000.0
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _chat_identity(event: Event) -> tuple[platform_entities.ChatType, str, typing.Any, str]:
    """Return chat type, chat id, group entity and sender id for a LINE event source."""
    source = event.source
    if isinstance(source, GroupSource):
        return (
            platform_entities.ChatType.GROUP,
            source.group_id,
            platform_entities.UserGroup(id=source.group_id, name=source.group_id),
            source.user_id or source.group_id,
        )
    if isinstance(source, RoomSource):
        # LINE rooms are multi-user chats; treat them as group chats keyed by room id.
        return (
            platform_entities.ChatType.GROUP,
            source.room_id,
            platform_entities.UserGroup(id=source.room_id, name=source.room_id),
            source.user_id or source.room_id,
        )
    user_id = source.user_id if isinstance(source, UserSource) else ''
    return platform_entities.ChatType.PRIVATE, user_id, None, user_id


class LineEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Convert LINE webhook events into unified EBA events and legacy message events."""

    def __init__(self, bot_account_id: str = '', blob_api: typing.Any = None):
        self.bot_account_id = bot_account_id
        self.blob_api = blob_api

    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2yiri(self, event: Event) -> typing.Optional[platform_events.EBAEvent]:
        """Convert one LINE webhook event into a unified event; None when unsupported."""
        common = dict(
            adapter_name=ADAPTER_NAME,
            timestamp=_timestamp(event),
            source_platform_object=event,
        )
        chat_type, chat_id, group, sender_id = _chat_identity(event)
        chat = dict(
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
        )
        if isinstance(event, MessageEvent):
            return platform_events.MessageReceivedEvent(
                **common,
                **chat,
                message_id=str(event.message.id),
                message_chain=await LineMessageConverter.target2yiri(
                    event, blob_api=self.blob_api, bot_account_id=self.bot_account_id
                ),
                sender=platform_entities.User(id=sender_id, nickname=sender_id),
            )
        if isinstance(event, UnsendEvent):
            return platform_events.MessageDeletedEvent(
                **common,
                **chat,
                message_id=str(event.unsend.message_id),
                operator=platform_entities.User(id=sender_id) if sender_id else None,
            )
        if isinstance(event, FollowEvent):
            return platform_events.PlatformSpecificEvent(
                **common, action='line.follow', data={**_event_payload(event), 'chat_id': chat_id}
            )
        if isinstance(event, UnfollowEvent):
            return platform_events.PlatformSpecificEvent(
                **common, action='line.unfollow', data={**_event_payload(event), 'chat_id': chat_id}
            )
        if isinstance(event, JoinEvent):
            return platform_events.BotInvitedToGroupEvent(
                **common,
                group=platform_entities.UserGroup(id=chat_id, name=chat_id),
            )
        if isinstance(event, LeaveEvent):
            return platform_events.BotRemovedFromGroupEvent(
                **common,
                group=platform_entities.UserGroup(id=chat_id, name=chat_id),
            )
        if isinstance(event, MemberJoinedEvent):
            member = _first_member(event.joined.members, chat_id)
            return platform_events.MemberJoinedEvent(**common, group=group, member=member)
        if isinstance(event, MemberLeftEvent):
            member = _first_member(event.left.members, chat_id)
            return platform_events.MemberLeftEvent(**common, group=group, member=member)
        if isinstance(event, PostbackEvent):
            return platform_events.PlatformSpecificEvent(
                **common,
                action='line.postback',
                data={
                    'data': event.postback.data,
                    'chat_type': chat_type.value,
                    'chat_id': chat_id,
                    'sender_id': sender_id,
                    **({'params': event.postback.params} if event.postback.params else {}),
                },
            )
        if isinstance(event, BeaconEvent):
            return platform_events.PlatformSpecificEvent(
                **common,
                action='line.beacon',
                data={'hwid': event.beacon.hwid, 'type': event.beacon.type, 'chat_id': chat_id},
            )
        # Remaining LINE event types stay visible to event processors without a lossy mapping.
        action = getattr(event, 'type', '') or type(event).__name__
        return platform_events.PlatformSpecificEvent(
            **common, action=f'line.{action}', data={**_event_payload(event), 'chat_id': chat_id}
        )

    async def target2legacy(self, event: Event) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
        """Build the legacy message event used by pipeline-based bindings."""
        eba_event = await self.target2yiri(event)
        if not isinstance(eba_event, platform_events.MessageReceivedEvent):
            return None
        return eba_event.to_legacy_event()


def _event_payload(event: Event) -> dict:
    to_dict = getattr(event, 'to_dict', None)
    if callable(to_dict):
        return dict(to_dict())
    return {}


def _first_member(members: typing.Any, fallback_id: str) -> platform_entities.User:
    """Member arrays carry only user ids; the first entry is the subject of the event."""
    for member in members or []:
        user_id = getattr(member, 'user_id', '') or ''
        if user_id:
            return platform_entities.User(id=user_id, nickname=user_id)
    return platform_entities.User(id=fallback_id, nickname=fallback_id)
