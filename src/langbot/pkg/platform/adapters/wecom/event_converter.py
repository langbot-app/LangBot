from __future__ import annotations

import typing

from langbot.libs.wecom_api.api import WecomClient
from langbot.libs.wecom_api.wecomevent import WecomEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.wecom.message_converter import WecomMessageConverter
from langbot.pkg.platform.adapters.wecom.types import ADAPTER_NAME, make_private_chat_id
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class WecomEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> WecomEvent | None:
        return getattr(event, 'source_platform_object', None)

    @staticmethod
    async def target2legacy(event: WecomEvent, bot: WecomClient | None = None) -> platform_events.FriendMessage | None:
        eba_event = await WecomEventConverter.target2yiri(event, bot)
        if hasattr(eba_event, 'to_legacy_event'):
            return eba_event.to_legacy_event()
        if event.type in {'text', 'image'} and eba_event is not None:
            friend = platform_entities.Friend(
                id=f'u{event.user_id}',
                nickname=getattr(getattr(eba_event, 'sender', None), 'nickname', str(event.user_id or '')),
                remark='',
            )
            return platform_events.FriendMessage(
                sender=friend,
                message_chain=eba_event.message_chain,
                time=getattr(eba_event, 'timestamp', None),
                source_platform_object=event,
            )
        return None

    @staticmethod
    async def target2yiri(event: WecomEvent, bot: WecomClient | None = None) -> platform_events.Event | None:
        if event.type in {'text', 'image'}:
            return await WecomEventConverter.message_to_eba(event, bot)
        return WecomEventConverter.platform_specific(event, f'message.{event.detail_type or event.type or "unknown"}')

    @staticmethod
    async def message_to_eba(event: WecomEvent, bot: WecomClient | None = None) -> platform_events.MessageReceivedEvent:
        if event.type == 'image':
            message_chain = await WecomMessageConverter.target2yiri_image(event.picurl, event.message_id)
        else:
            message_chain = await WecomMessageConverter.target2yiri_text(event.message, event.message_id)

        sender = await WecomEventConverter.user_from_event(event, bot)
        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.message_id or '',
            message_chain=message_chain,
            sender=sender,
            chat_type=platform_entities.ChatType.PRIVATE,
            chat_id=make_private_chat_id(event.user_id, event.agent_id),
            group=None,
            timestamp=float(event.timestamp or 0),
            source_platform_object=event,
        )

    @staticmethod
    async def user_from_event(event: WecomEvent, bot: WecomClient | None = None) -> platform_entities.User:
        nickname = str(event.user_id or '')
        raw: dict[str, typing.Any] = {}
        if bot and event.user_id:
            try:
                raw = await bot.get_user_info(event.user_id)
                nickname = raw.get('name') or nickname
            except Exception:
                raw = {}

        return platform_entities.User(
            id=event.user_id or '',
            nickname=nickname,
            username=raw.get('alias') or raw.get('userid') or None,
        )

    @staticmethod
    def platform_specific(event: WecomEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=float(event.timestamp or 0),
            source_platform_object=event,
        )
