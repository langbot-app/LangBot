from __future__ import annotations

import typing

import aiocqhttp

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.aiocqhttp.message_converter import AiocqhttpMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


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
            return AiocqhttpEventConverter.notice_to_eba(event, bot_user_id)
        if event_type == 'request':
            return AiocqhttpEventConverter.request_to_eba(event)
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
            group = AiocqhttpEventConverter.group_from_event(event)

        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name='aiocqhttp',
            message_id=getattr(event, 'message_id', ''),
            message_chain=message_chain,
            sender=AiocqhttpEventConverter.user_from_sender(event),
            chat_type=chat_type,
            chat_id=chat_id,
            group=group,
            timestamp=float(getattr(event, 'time', 0) or 0),
            source_platform_object=event,
        )

    @staticmethod
    def notice_to_eba(
        event: aiocqhttp.Event,
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
                group=AiocqhttpEventConverter.group_from_event(event) if notice_type == 'group_recall' else None,
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        if notice_type == 'group_increase':
            group = AiocqhttpEventConverter.group_from_event(event)
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
            group = AiocqhttpEventConverter.group_from_event(event)
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
            group = AiocqhttpEventConverter.group_from_event(event)
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
    def request_to_eba(event: aiocqhttp.Event) -> platform_events.EBAEvent:
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
                group=AiocqhttpEventConverter.group_from_event(event),
                inviter=AiocqhttpEventConverter.user(getattr(event, 'user_id', '')),
                request_id=getattr(event, 'flag', ''),
                timestamp=float(getattr(event, 'time', 0) or 0),
                source_platform_object=event,
            )
        return AiocqhttpEventConverter.platform_specific(event, f'request.{request_type}')

    @staticmethod
    def user_from_sender(event: aiocqhttp.Event) -> platform_entities.User:
        sender = getattr(event, 'sender', {}) or {}
        nickname = sender.get('card') or sender.get('nickname') or ''
        return platform_entities.User(
            id=sender.get('user_id', getattr(event, 'user_id', '')),
            nickname=nickname,
            remark=sender.get('remark'),
        )

    @staticmethod
    def user(user_id: typing.Union[int, str, None], nickname: str = '') -> platform_entities.User | None:
        if user_id is None or user_id == '':
            return None
        return platform_entities.User(id=user_id, nickname=nickname)

    @staticmethod
    def group_from_event(event: aiocqhttp.Event) -> platform_entities.UserGroup:
        return platform_entities.UserGroup(
            id=getattr(event, 'group_id', ''),
            name=getattr(event, 'group_name', '') or '',
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
