from __future__ import annotations

import typing

from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.dingtalk.message_converter import DingTalkMessageConverter
from langbot.pkg.platform.adapters.dingtalk.types import ADAPTER_NAME
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class DingTalkEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event):
        return getattr(event, 'source_platform_object', None)

    @staticmethod
    async def target2yiri(event: DingTalkEvent, bot_name: str) -> platform_events.Event | None:
        if event.conversation in {'FriendMessage', 'GroupMessage'}:
            return await DingTalkEventConverter.message_to_eba(event, bot_name)
        return DingTalkEventConverter.platform_specific(event, f'message.{event.conversation or "unknown"}')

    @staticmethod
    async def target2legacy(
        event: DingTalkEvent,
        bot_name: str,
    ) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
        eba_event = await DingTalkEventConverter.message_to_eba(event, bot_name)
        if eba_event:
            return eba_event.to_legacy_event()
        return None

    @staticmethod
    async def message_to_eba(event: DingTalkEvent, bot_name: str) -> platform_events.MessageReceivedEvent:
        incoming_message = event.incoming_message
        message_chain = await DingTalkMessageConverter.target2yiri(event, bot_name)
        sender = DingTalkEventConverter.user_from_event(event)
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = getattr(incoming_message, 'sender_staff_id', '')
        group = None
        if event.conversation == 'GroupMessage':
            chat_type = platform_entities.ChatType.GROUP
            chat_id = getattr(incoming_message, 'conversation_id', '')
            group = DingTalkEventConverter.group_from_event(event)

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=getattr(incoming_message, 'message_id', ''),
            message_chain=message_chain,
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
            timestamp=DingTalkEventConverter._timestamp(incoming_message),
            source_platform_object=event,
        )

    @staticmethod
    def user_from_event(event: DingTalkEvent) -> platform_entities.User:
        incoming_message = event.incoming_message
        return platform_entities.User(
            id=getattr(incoming_message, 'sender_staff_id', ''),
            nickname=getattr(incoming_message, 'sender_nick', '') or '',
        )

    @staticmethod
    def group_from_event(event: DingTalkEvent) -> platform_entities.UserGroup:
        incoming_message = event.incoming_message
        return platform_entities.UserGroup(
            id=getattr(incoming_message, 'conversation_id', ''),
            name=getattr(incoming_message, 'conversation_title', '') or '',
        )

    @staticmethod
    def platform_specific(event: DingTalkEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data={
                key: value for key, value in dict(event).items() if key not in {'IncomingMessage', 'Picture', 'Audio'}
            },
            timestamp=DingTalkEventConverter._timestamp(event.incoming_message),
            source_platform_object=event,
        )

    @staticmethod
    def _timestamp(incoming_message: typing.Any) -> float:
        value = getattr(incoming_message, 'create_at', None)
        if isinstance(value, (int, float)):
            timestamp = float(value)
            return timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
        if hasattr(value, 'timestamp'):
            return float(value.timestamp())
        return 0.0
