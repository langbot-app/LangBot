from __future__ import annotations

import asyncio
import time
import typing

import aiocqhttp

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.aiocqhttp.message_converter import AiocqhttpMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


_GROUP_NAME_CACHE_TTL_SECONDS = 3600
_GROUP_NAME_NEGATIVE_CACHE_TTL_SECONDS = 60
_GROUP_NAME_LOOKUP_TIMEOUT_SECONDS = 2
_GROUP_MEMBER_INFO_CACHE_TTL_SECONDS = 86400
_GROUP_MEMBER_INFO_NEGATIVE_CACHE_TTL_SECONDS = 600
_GROUP_MEMBER_INFO_LOOKUP_TIMEOUT_SECONDS = 2

_group_name_cache: dict[typing.Union[int, str], tuple[str, float]] = {}
_group_name_negative_cache: dict[typing.Union[int, str], float] = {}
_group_member_info_cache: dict[tuple[typing.Union[int, str], typing.Union[int, str]], tuple[dict, float]] = {}
_group_member_info_negative_cache: dict[tuple[typing.Union[int, str], typing.Union[int, str]], float] = {}


def _get_field(data: dict, key: str, default: str = '') -> str:
    value = data.get(key)
    if value is None:
        return default
    return str(value)


def _get_group_member_name(sender: dict) -> str:
    return _get_field(sender, 'card') or _get_field(sender, 'nickname') or _get_field(sender, 'user_id')


def _get_group_name_placeholder(group_id: typing.Union[int, str]) -> str:
    return f'Group {group_id}'


async def _get_group_name(group_id: typing.Union[int, str], bot: aiocqhttp.CQHttp | None = None) -> str:
    now = time.monotonic()
    if group_id in _group_name_cache:
        group_name, expires_at = _group_name_cache[group_id]
        if expires_at > now:
            return group_name
        del _group_name_cache[group_id]
    if group_id in _group_name_negative_cache:
        expires_at = _group_name_negative_cache[group_id]
        if expires_at > now:
            return ''
        del _group_name_negative_cache[group_id]
    if bot is None:
        return ''
    try:
        group_info = await asyncio.wait_for(
            bot.get_group_info(group_id=group_id),
            timeout=_GROUP_NAME_LOOKUP_TIMEOUT_SECONDS,
        )
    except Exception:
        _group_name_negative_cache[group_id] = now + _GROUP_NAME_NEGATIVE_CACHE_TTL_SECONDS
        return ''
    group_name = _get_field(group_info, 'group_name') if isinstance(group_info, dict) else ''
    if group_name:
        _group_name_cache[group_id] = (group_name, now + _GROUP_NAME_CACHE_TTL_SECONDS)
        _group_name_negative_cache.pop(group_id, None)
    else:
        _group_name_negative_cache[group_id] = now + _GROUP_NAME_NEGATIVE_CACHE_TTL_SECONDS
    return group_name


async def _get_group_member_info(
    group_id: typing.Union[int, str],
    user_id: typing.Union[int, str],
    bot: aiocqhttp.CQHttp | None = None,
) -> dict:
    now = time.monotonic()
    cache_key = (group_id, user_id)
    if cache_key in _group_member_info_cache:
        member_info, expires_at = _group_member_info_cache[cache_key]
        if expires_at > now:
            return member_info
        del _group_member_info_cache[cache_key]
    if cache_key in _group_member_info_negative_cache:
        expires_at = _group_member_info_negative_cache[cache_key]
        if expires_at > now:
            return {}
        del _group_member_info_negative_cache[cache_key]
    if bot is None:
        return {}
    try:
        member_info = await asyncio.wait_for(
            bot.get_group_member_info(group_id=group_id, user_id=user_id),
            timeout=_GROUP_MEMBER_INFO_LOOKUP_TIMEOUT_SECONDS,
        )
    except Exception:
        _group_member_info_negative_cache[cache_key] = now + _GROUP_MEMBER_INFO_NEGATIVE_CACHE_TTL_SECONDS
        return {}
    if isinstance(member_info, dict) and member_info:
        _group_member_info_cache[cache_key] = (
            member_info,
            now + _GROUP_MEMBER_INFO_CACHE_TTL_SECONDS,
        )
        _group_member_info_negative_cache.pop(cache_key, None)
        return member_info
    _group_member_info_negative_cache[cache_key] = now + _GROUP_MEMBER_INFO_NEGATIVE_CACHE_TTL_SECONDS
    return {}


class AiocqhttpEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event, bot_account_id: int | str | None = None):
        return getattr(event, 'source_platform_object', None)

    @staticmethod
    async def target2yiri(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
        bot_user_id: int | str | None = None,
    ) -> platform_events.Event | None:
        event_type = getattr(event, 'type', None)
        if event_type == 'message':
            return await AiocqhttpEventConverter.message_to_eba(event, bot)
        if event_type == 'notice':
            return await AiocqhttpEventConverter.notice_to_eba(event, bot, bot_user_id)
        if event_type == 'request':
            return await AiocqhttpEventConverter.request_to_eba(event, bot)
        if event_type == 'meta_event':
            return AiocqhttpEventConverter.platform_specific(event, f'meta.{getattr(event, "detail_type", "")}')
        return None

    @staticmethod
    async def target2legacy(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
    ) -> platform_events.FriendMessage | platform_events.GroupMessage | None:
        eba_event = await AiocqhttpEventConverter.message_to_eba(event, bot)
        if eba_event:
            return eba_event.to_legacy_event()
        return None

    @staticmethod
    async def message_to_eba(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
    ) -> platform_events.MessageReceivedEvent:
        message_chain = await AiocqhttpMessageConverter.target2yiri(
            getattr(event, 'message', []),
            getattr(event, 'message_id', -1),
            getattr(event, 'time', None),
            bot,
        )
        message_type = getattr(event, 'message_type', getattr(event, 'detail_type', 'private'))
        group = None
        chat_type = platform_entities.ChatType.PRIVATE
        chat_id = getattr(event, 'user_id', '')
        if message_type == 'group':
            chat_type = platform_entities.ChatType.GROUP
            chat_id = getattr(event, 'group_id', '')
            group = await AiocqhttpEventConverter.group_from_event(event, bot)

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name='aiocqhttp',
            message_id=getattr(event, 'message_id', ''),
            message_chain=message_chain,
            sender=await AiocqhttpEventConverter.user_from_sender(event, bot),
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
            timestamp=float(getattr(event, 'time', 0) or 0),
            source_platform_object=event,
        )

    @staticmethod
    async def notice_to_eba(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
        bot_user_id: int | str | None = None,
    ) -> platform_events.EBAEvent:
        notice_type = getattr(event, 'notice_type', getattr(event, 'detail_type', ''))
        if notice_type in ('group_recall', 'friend_recall'):
            return platform_events.MessageDeletedEvent(
                type='message.deleted',
                adapter_name='aiocqhttp',
                message_id=getattr(event, 'message_id', ''),
                operator=AiocqhttpEventConverter.user(getattr(event, 'operator_id', None)),
                chat_type=platform_entities.ChatType.GROUP
                if notice_type == 'group_recall'
                else platform_entities.ChatType.PRIVATE,
                chat_id=getattr(event, 'group_id', getattr(event, 'user_id', '')),
                group=await AiocqhttpEventConverter.group_from_event(event, bot)
                if notice_type == 'group_recall'
                else None,
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        if notice_type == 'group_increase':
            group = await AiocqhttpEventConverter.group_from_event(event, bot)
            user = AiocqhttpEventConverter.user(getattr(event, 'user_id', ''))
            inviter_id = getattr(event, 'operator_id', None)
            if AiocqhttpEventConverter._is_bot_user(getattr(event, 'user_id', None), bot_user_id, event):
                return platform_events.BotInvitedToGroupEvent(
                    type='bot.invited_to_group',
                    adapter_name='aiocqhttp',
                    group=group,
                    inviter=AiocqhttpEventConverter.user(inviter_id) if inviter_id else None,
                    timestamp=float(getattr(event, 'time', 0) or 0),
                    source_platform_object=event,
                )
            return platform_events.MemberJoinedEvent(
                type='group.member_joined',
                adapter_name='aiocqhttp',
                group=group,
                member=user,
                inviter=AiocqhttpEventConverter.user(inviter_id) if inviter_id else None,
                join_type=getattr(event, 'sub_type', None) or 'direct',
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        if notice_type == 'group_decrease':
            group = await AiocqhttpEventConverter.group_from_event(event, bot)
            operator = AiocqhttpEventConverter.user(getattr(event, 'operator_id', None))
            if AiocqhttpEventConverter._is_bot_user(getattr(event, 'user_id', None), bot_user_id, event):
                return platform_events.BotRemovedFromGroupEvent(
                    type='bot.removed_from_group',
                    adapter_name='aiocqhttp',
                    group=group,
                    operator=operator,
                    timestamp=float(getattr(event, 'time', 0) or 0),
                    source_platform_object=event,
                )
            return platform_events.MemberLeftEvent(
                type='group.member_left',
                adapter_name='aiocqhttp',
                group=group,
                member=AiocqhttpEventConverter.user(getattr(event, 'user_id', '')),
                is_kicked=getattr(event, 'sub_type', '') in ('kick', 'kick_me'),
                operator=operator,
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        if notice_type == 'group_ban':
            group = await AiocqhttpEventConverter.group_from_event(event, bot)
            duration = int(getattr(event, 'duration', 0) or 0)
            operator = AiocqhttpEventConverter.user(getattr(event, 'operator_id', None))
            if AiocqhttpEventConverter._is_bot_user(getattr(event, 'user_id', None), bot_user_id, event):
                event_cls = platform_events.BotMutedEvent if duration > 0 else platform_events.BotUnmutedEvent
                kwargs: dict[str, typing.Any] = {
                    'type': 'bot.muted' if duration > 0 else 'bot.unmuted',
                    'adapter_name': 'aiocqhttp',
                    'group': group,
                    'operator': operator,
                    'timestamp': float(getattr(event, 'time', 0) or 0),
                    'source_platform_object': event,
                }
                if duration > 0:
                    kwargs['duration'] = duration
                return event_cls(**kwargs)
            if duration > 0:
                return platform_events.MemberBannedEvent(
                    type='group.member_banned',
                    adapter_name='aiocqhttp',
                    group=group,
                    member=AiocqhttpEventConverter.user(getattr(event, 'user_id', '')),
                    operator=operator,
                    duration=duration,
                    timestamp=float(getattr(event, 'time', 0) or 0),
                    source_platform_object=event,
                )
        if notice_type == 'friend_add':
            return platform_events.FriendAddedEvent(
                type='friend.added',
                adapter_name='aiocqhttp',
                user=AiocqhttpEventConverter.user(getattr(event, 'user_id', '')),
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        return AiocqhttpEventConverter.platform_specific(event, f'notice.{notice_type}')

    @staticmethod
    async def request_to_eba(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
    ) -> platform_events.EBAEvent:
        request_type = getattr(event, 'request_type', getattr(event, 'detail_type', ''))
        if request_type == 'friend':
            return platform_events.FriendRequestReceivedEvent(
                type='friend.request_received',
                adapter_name='aiocqhttp',
                request_id=getattr(event, 'flag', ''),
                user=AiocqhttpEventConverter.user(getattr(event, 'user_id', '')),
                message=getattr(event, 'comment', None),
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        if request_type == 'group' and getattr(event, 'sub_type', '') == 'invite':
            return platform_events.BotInvitedToGroupEvent(
                type='bot.invited_to_group',
                adapter_name='aiocqhttp',
                group=await AiocqhttpEventConverter.group_from_event(event, bot),
                inviter=AiocqhttpEventConverter.user(getattr(event, 'user_id', '')),
                request_id=getattr(event, 'flag', ''),
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        return AiocqhttpEventConverter.platform_specific(event, f'request.{request_type}')

    @staticmethod
    async def user_from_sender(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
    ) -> platform_entities.User:
        sender = getattr(event, 'sender', {}) or {}
        user_id = sender.get('user_id', getattr(event, 'user_id', ''))
        has_sender_display_name = bool(_get_field(sender, 'card') or _get_field(sender, 'nickname'))
        nickname = _get_group_member_name(sender)
        remark = sender.get('remark')
        if (
            getattr(event, 'message_type', getattr(event, 'detail_type', 'private')) == 'group'
            and user_id
            and (not has_sender_display_name or not remark)
        ):
            member_info = await _get_group_member_info(getattr(event, 'group_id', ''), user_id, bot)
            remark = _get_field(member_info, 'card') or _get_field(member_info, 'remark') or None
            if not has_sender_display_name:
                nickname = _get_group_member_name(member_info) or nickname
        return platform_entities.User(
            id=user_id,
            nickname=nickname,
            remark=remark,
        )

    @staticmethod
    def user(user_id: typing.Union[int, str, None], nickname: str = '') -> platform_entities.User | None:
        if user_id is None or user_id == '':
            return None
        return platform_entities.User(id=user_id, nickname=nickname)

    @staticmethod
    async def group_from_event(
        event: aiocqhttp.Event,
        bot: aiocqhttp.CQHttp | None = None,
    ) -> platform_entities.UserGroup:
        group_id = getattr(event, 'group_id', '')
        group_name = getattr(event, 'group_name', '') or ''
        if group_id and not group_name:
            group_name = await _get_group_name(group_id, bot)
        if group_id and not group_name:
            group_name = _get_group_name_placeholder(group_id)
        return platform_entities.UserGroup(
            id=group_id,
            name=group_name,
            member_count=getattr(event, 'member_count', None),
        )

    @staticmethod
    def platform_specific(event: aiocqhttp.Event, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name='aiocqhttp',
            action=action,
            data={key: value for key, value in dict(event).items() if key not in {'message'}},
            timestamp=float(getattr(event, 'time', 0) or 0),
            source_platform_object=event,
        )

    @staticmethod
    def _is_bot_user(user_id: typing.Any, bot_user_id: typing.Any, event: aiocqhttp.Event) -> bool:
        candidate = bot_user_id or getattr(event, 'self_id', None)
        return candidate is not None and user_id is not None and str(user_id) == str(candidate)
