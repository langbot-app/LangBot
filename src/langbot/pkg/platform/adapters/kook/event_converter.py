from __future__ import annotations

import time

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.kook.message_converter import KookMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class KookEventConverter(abstract_platform_adapter.AbstractEventConverter):
    MESSAGE_TYPES = {1, 2, 4, 8, 9, 10}

    @staticmethod
    async def yiri2target(event: platform_events.Event):
        raise NotImplementedError

    @staticmethod
    async def target2yiri(kook_event: dict, bot_account_id: str = '') -> platform_events.Event | None:
        event_type = int(kook_event.get('type', 0) or 0)
        channel_type = kook_event.get('channel_type')
        if event_type in KookEventConverter.MESSAGE_TYPES and channel_type in {'GROUP', 'PERSON'}:
            return await KookEventConverter.message_to_eba(kook_event, bot_account_id)

        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name='kook',
            action=str(kook_event.get('type') or 'gateway_event'),
            data=KookEventConverter._compact_data(kook_event),
            timestamp=KookEventConverter._timestamp(kook_event),
            source_platform_object=kook_event,
        )

    @staticmethod
    async def message_to_eba(kook_event: dict, bot_account_id: str = '') -> platform_events.MessageReceivedEvent:
        channel_type = kook_event.get('channel_type')
        author = KookEventConverter._author(kook_event)
        chat_type = platform_entities.ChatType.PRIVATE if channel_type == 'PERSON' else platform_entities.ChatType.GROUP
        chat_id = KookEventConverter._chat_id(kook_event)
        group = None
        if chat_type == platform_entities.ChatType.GROUP:
            group = KookEventConverter._group(kook_event)

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name='kook',
            message_id=str(kook_event.get('msg_id') or ''),
            message_chain=await KookMessageConverter.target2yiri(kook_event, bot_account_id),
            sender=author,
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
            timestamp=KookEventConverter._timestamp(kook_event),
            source_platform_object=kook_event,
        )

    @staticmethod
    async def target2legacy(
        kook_event: dict, bot_account_id: str = ''
    ) -> platform_events.FriendMessage | platform_events.GroupMessage:
        eba_event = await KookEventConverter.message_to_eba(kook_event, bot_account_id)
        return eba_event.to_legacy_event()

    @staticmethod
    def _author(kook_event: dict) -> platform_entities.User:
        extra = kook_event.get('extra') or {}
        author = extra.get('author') or {}
        user_id = str(kook_event.get('author_id') or author.get('id') or '')
        return platform_entities.User(
            id=user_id,
            nickname=str(author.get('nickname') or author.get('username') or user_id),
            username=author.get('username'),
            avatar_url=author.get('avatar'),
            is_bot=bool(author.get('bot', False)),
            remark=user_id,
        )

    @staticmethod
    def _group(kook_event: dict) -> platform_entities.UserGroup:
        extra = kook_event.get('extra') or {}
        return platform_entities.UserGroup(
            id=str(kook_event.get('target_id') or ''),
            name=str(extra.get('channel_name') or kook_event.get('target_id') or ''),
            description=extra.get('guild_name'),
            owner_id=extra.get('guild_id'),
        )

    @staticmethod
    def _chat_id(kook_event: dict) -> str:
        if kook_event.get('channel_type') == 'PERSON':
            extra = kook_event.get('extra') or {}
            return str(extra.get('code') or kook_event.get('author_id') or kook_event.get('target_id') or '')
        return str(kook_event.get('target_id') or '')

    @staticmethod
    def _timestamp(kook_event: dict) -> float:
        raw_timestamp = kook_event.get('msg_timestamp') or time.time()
        timestamp = float(raw_timestamp)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        return timestamp

    @staticmethod
    def _compact_data(kook_event: dict) -> dict:
        return {
            'type': kook_event.get('type'),
            'channel_type': kook_event.get('channel_type'),
            'target_id': kook_event.get('target_id'),
            'author_id': kook_event.get('author_id'),
            'msg_id': kook_event.get('msg_id'),
        }
