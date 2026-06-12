from __future__ import annotations

import typing

from langbot.libs.wecom_customer_service_api.api import WecomCSClient
from langbot.libs.wecom_customer_service_api.wecomcsevent import WecomCSEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.wecomcs.message_converter import WecomCSMessageConverter
from langbot.pkg.platform.adapters.wecomcs.types import ADAPTER_NAME, make_private_chat_id
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class WecomCSEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> WecomCSEvent | None:
        return getattr(event, 'source_platform_object', None)

    @staticmethod
    async def target2legacy(event: WecomCSEvent, bot: WecomCSClient | None = None) -> platform_events.FriendMessage | None:
        eba_event = await WecomCSEventConverter.target2yiri(event, bot)
        if hasattr(eba_event, 'to_legacy_event'):
            return eba_event.to_legacy_event()
        return None

    @staticmethod
    async def target2yiri(event: WecomCSEvent, bot: WecomCSClient | None = None) -> platform_events.Event | None:
        if event.type in {'text', 'image', 'file', 'voice'}:
            return await WecomCSEventConverter.message_to_eba(event, bot)
        return WecomCSEventConverter.platform_specific(event, f'wecomcs.{event.type or "unknown"}')

    @staticmethod
    async def message_to_eba(event: WecomCSEvent, bot: WecomCSClient | None = None) -> platform_events.MessageReceivedEvent:
        message_chain = await WecomCSMessageConverter.target2yiri(event)
        sender = await WecomCSEventConverter.user_from_event(event, bot)
        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.message_id or '',
            message_chain=message_chain,
            sender=sender,
            chat_type=platform_entities.ChatType.PRIVATE,
            chat_id=make_private_chat_id(event.user_id, event.receiver_id),
            group=None,
            timestamp=float(event.timestamp or 0),
            source_platform_object=event,
        )

    @staticmethod
    async def user_from_event(event: WecomCSEvent, bot: WecomCSClient | None = None) -> platform_entities.User:
        nickname = str(event.user_id or '')
        avatar_url = None
        raw: dict[str, typing.Any] = {}
        if bot and event.user_id:
            try:
                raw = await bot.get_customer_info(event.user_id) or {}
                nickname = raw.get('nickname') or nickname
                avatar_url = raw.get('avatar')
            except Exception:
                raw = {}

        return platform_entities.User(
            id=event.user_id or '',
            nickname=nickname,
            avatar_url=avatar_url,
            username=raw.get('external_userid') or None,
        )

    @staticmethod
    def platform_specific(event: WecomCSEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=float(event.timestamp or 0),
            source_platform_object=event,
        )
