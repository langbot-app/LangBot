from __future__ import annotations

import time
import typing

import lark_oapi
from lark_oapi.api.im.v1 import EventMessage, GetMessageRequest, Message

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot.pkg.platform.adapters.lark.types import ADAPTER_NAME
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class LarkEventConverter(abstract_platform_adapter.AbstractEventConverter):
    _processed_thread_quote_cache: typing.ClassVar[dict[str, float]] = {}
    _processed_thread_quote_cache_max_size: typing.ClassVar[int] = 4096
    _processed_thread_quote_cache_ttl_seconds: typing.ClassVar[int] = 86400

    @staticmethod
    async def yiri2target(event: platform_events.Event):
        return getattr(event, 'source_platform_object', None)

    @staticmethod
    async def target2yiri(
        event: lark_oapi.im.v1.P2ImMessageReceiveV1,
        api_client: lark_oapi.Client,
    ) -> platform_events.Event | None:
        return await LarkEventConverter.message_to_eba(event, api_client)

    @staticmethod
    async def target2legacy(
        event: lark_oapi.im.v1.P2ImMessageReceiveV1,
        api_client: lark_oapi.Client,
    ) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
        eba_event = await LarkEventConverter.message_to_eba(event, api_client)
        if eba_event:
            return eba_event.to_legacy_event()
        return None

    @staticmethod
    async def message_to_eba(
        event: lark_oapi.im.v1.P2ImMessageReceiveV1,
        api_client: lark_oapi.Client,
    ) -> platform_events.MessageReceivedEvent:
        message = event.event.message
        message_chain = await LarkMessageConverter.target2yiri(message, api_client)
        await LarkEventConverter._append_quote_content(message, message_chain, api_client)

        sender = LarkEventConverter.user_from_event(event)
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = LarkEventConverter.sender_id(event)
        group = None
        if getattr(message, 'chat_type', '') == 'group':
            chat_type = platform_entities.ChatType.GROUP
            chat_id = getattr(message, 'chat_id', '') or chat_id
            group = platform_entities.UserGroup(id=chat_id, name='')

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=getattr(message, 'message_id', ''),
            message_chain=message_chain,
            sender=sender,
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
            timestamp=LarkEventConverter._timestamp(getattr(message, 'create_time', None)),
            source_platform_object=event,
        )

    @staticmethod
    def user_from_event(event: lark_oapi.im.v1.P2ImMessageReceiveV1) -> platform_entities.User:
        sender_id = getattr(getattr(event.event.sender, 'sender_id', None), 'open_id', '') or ''
        union_id = getattr(getattr(event.event.sender, 'sender_id', None), 'union_id', '') or ''
        return platform_entities.User(id=sender_id, nickname=union_id)

    @staticmethod
    def sender_id(event: lark_oapi.im.v1.P2ImMessageReceiveV1) -> str:
        return getattr(getattr(event.event.sender, 'sender_id', None), 'open_id', '') or ''

    @staticmethod
    def bot_invited_to_group(
        raw_event: typing.Any,
        chat_id: str,
        operator_id: str | None = None,
    ) -> platform_events.BotInvitedToGroupEvent:
        return platform_events.BotInvitedToGroupEvent(
            type='bot.invited_to_group',
            adapter_name=ADAPTER_NAME,
            group=platform_entities.UserGroup(id=chat_id, name=''),
            inviter=platform_entities.User(id=operator_id) if operator_id else None,
            timestamp=time.time(),
            source_platform_object=raw_event,
        )

    @staticmethod
    def platform_specific(
        raw_event: typing.Any, action: str, data: dict | None = None
    ) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=data or {},
            timestamp=time.time(),
            source_platform_object=raw_event,
        )

    @classmethod
    def _prune_processed_thread_quote_cache(cls, now: float | None = None) -> None:
        if now is None:
            now = time.time()
        expire_before = now - cls._processed_thread_quote_cache_ttl_seconds
        while cls._processed_thread_quote_cache:
            oldest_key, oldest_ts = next(iter(cls._processed_thread_quote_cache.items()))
            if oldest_ts >= expire_before:
                break
            cls._processed_thread_quote_cache.pop(oldest_key, None)
        while len(cls._processed_thread_quote_cache) > cls._processed_thread_quote_cache_max_size:
            cls._processed_thread_quote_cache.pop(next(iter(cls._processed_thread_quote_cache)), None)

    @classmethod
    def _extract_quote_message_id(cls, message: EventMessage) -> str | None:
        parent_id = getattr(message, 'parent_id', None)
        if not parent_id or parent_id == getattr(message, 'message_id', None):
            return None
        thread_id = getattr(message, 'thread_id', None)
        if thread_id:
            cls._prune_processed_thread_quote_cache()
            if thread_id in cls._processed_thread_quote_cache:
                return None
            cls._processed_thread_quote_cache[thread_id] = time.time()
        return parent_id

    @staticmethod
    async def _append_quote_content(
        message: EventMessage,
        message_chain: platform_message.MessageChain,
        api_client: lark_oapi.Client,
    ) -> None:
        quote_message_id = LarkEventConverter._extract_quote_message_id(message)
        if not quote_message_id:
            return
        quote_chain = await LarkEventConverter._fetch_quoted_message(quote_message_id, api_client)
        if not quote_chain:
            return
        origin = platform_message.MessageChain(
            [comp for comp in quote_chain if not isinstance(comp, platform_message.Source)]
        )
        message_chain.append(
            platform_message.Quote(
                id=quote_message_id,
                group_id=getattr(message, 'chat_id', None),
                target_id=getattr(message, 'chat_id', None),
                origin=origin,
            )
        )

    @staticmethod
    async def _fetch_quoted_message(
        quote_message_id: str,
        api_client: lark_oapi.Client,
    ) -> platform_message.MessageChain | None:
        request = GetMessageRequest.builder().message_id(quote_message_id).build()
        response = await api_client.im.v1.message.aget(request)
        if not response.success() or not getattr(response.data, 'items', None):
            return None
        event_message = LarkEventConverter._build_event_message_from_message_item(response.data.items[0])
        if event_message is None:
            return None
        return await LarkMessageConverter.target2yiri(event_message, api_client)

    @staticmethod
    def _build_event_message_from_message_item(message_item: Message) -> EventMessage | None:
        body = getattr(message_item, 'body', None)
        content = getattr(body, 'content', None) if body else None
        if not content:
            return None
        event_data = {
            'message_id': message_item.message_id,
            'message_type': message_item.msg_type,
            'content': content,
            'create_time': message_item.create_time,
            'mentions': getattr(message_item, 'mentions', []) or [],
        }
        for key in ('parent_id', 'root_id', 'thread_id', 'chat_id'):
            value = getattr(message_item, key, None)
            if value:
                event_data[key] = value
        return EventMessage(event_data)

    @staticmethod
    def _timestamp(value: typing.Any) -> float:
        if isinstance(value, (int, float, str)):
            try:
                timestamp = float(value)
                return timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
            except ValueError:
                pass
        if hasattr(value, 'timestamp'):
            return float(value.timestamp())
        return 0.0
