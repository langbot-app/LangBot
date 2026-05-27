from __future__ import annotations

import time
import typing

from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot.pkg.platform.adapters.wecombot.message_converter import WecomBotMessageConverter
from langbot.pkg.platform.adapters.wecombot.types import ADAPTER_NAME
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class WecomBotEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self, bot_name: str = ''):
        self.bot_name = bot_name

    @staticmethod
    async def yiri2target(event: platform_events.Event) -> typing.Any:
        return getattr(event, 'source_platform_object', None)

    async def target2legacy(self, event: WecomBotEvent) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
        eba_event = await self.target2yiri(event)
        if not isinstance(eba_event, platform_events.MessageReceivedEvent):
            return None
        if eba_event.chat_type == platform_entities.ChatType.PRIVATE:
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(id=eba_event.sender.id, nickname=eba_event.sender.nickname, remark=''),
                message_chain=eba_event.message_chain,
                time=eba_event.timestamp,
                source_platform_object=event,
            )
        return platform_events.GroupMessage(
            sender=platform_entities.GroupMember(
                id=eba_event.sender.id,
                permission='MEMBER',
                member_name=eba_event.sender.nickname,
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

    async def target2yiri(self, event: WecomBotEvent) -> platform_events.Event:
        if event.type in {'single', 'group'} and event.msgtype != 'event':
            return await self.message_to_eba(event)
        return self.platform_specific(event, f'wecombot.{event.get("eventtype") or event.msgtype or event.type or "unknown"}')

    async def message_to_eba(self, event: WecomBotEvent) -> platform_events.MessageReceivedEvent:
        sender = platform_entities.User(id=event.userid, nickname=event.username or event.userid)
        group = None
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = event.userid
        if event.type == 'group':
            chat_type = platform_entities.ChatType.GROUP
            chat_id = str(event.chatid)
            group = platform_entities.UserGroup(id=str(event.chatid), name=event.chatname or str(event.chatid))

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.message_id or '',
            message_chain=await WecomBotMessageConverter.target2yiri(event, self.bot_name),
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id or '',
            group=group,
            timestamp=time.time(),
            source_platform_object=event,
        )

    @staticmethod
    def feedback_to_eba(
        *,
        feedback_id: str,
        feedback_type: int,
        feedback_content: str | None = None,
        inaccurate_reasons: list | None = None,
        session=None,
    ) -> platform_events.FeedbackReceivedEvent:
        session_id = None
        user_id = None
        message_id = None
        stream_id = None
        if session:
            if getattr(session, 'chat_id', None):
                session_id = f'group_{session.chat_id}'
            elif getattr(session, 'user_id', None):
                session_id = f'person_{session.user_id}'
            user_id = getattr(session, 'user_id', None)
            message_id = getattr(session, 'msg_id', None)
            stream_id = getattr(session, 'stream_id', None)

        return platform_events.FeedbackReceivedEvent(
            type='feedback.received',
            adapter_name=ADAPTER_NAME,
            feedback_id=feedback_id,
            feedback_type=feedback_type,
            feedback_content=feedback_content,
            inaccurate_reasons=[str(reason) for reason in (inaccurate_reasons or [])] or None,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            stream_id=stream_id,
            timestamp=time.time(),
            source_platform_object=session,
        )

    @staticmethod
    def platform_specific(event: WecomBotEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=time.time(),
            source_platform_object=event,
        )
