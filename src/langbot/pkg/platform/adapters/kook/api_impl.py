from __future__ import annotations

import typing

from langbot.pkg.platform.adapters.kook.message_converter import KookMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot.pkg.platform.adapters.kook.errors import NotSupportedError


class KookAPIMixin:
    _message_cache: dict[str, platform_events.MessageReceivedEvent]
    _user_cache: dict[str, platform_entities.User]
    _group_cache: dict[str, platform_entities.UserGroup]

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        content, msg_type = await KookMessageConverter.yiri2target(message)
        endpoint = '/message/create' if target_type.lower() in {'group', 'channel'} else '/direct-message/create'
        raw = await self._request(
            'POST',
            endpoint,
            json={
                'target_id': str(target_id),
                'content': content,
                'type': msg_type,
            },
        )
        data = raw.get('data') or {}
        return platform_events.MessageResult(message_id=data.get('msg_id'), raw=raw)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        content, msg_type = await KookMessageConverter.yiri2target(message)
        kook_event = message_source.source_platform_object or {}
        channel_type = kook_event.get('channel_type')
        msg_id = kook_event.get('msg_id')

        if channel_type == 'GROUP':
            endpoint = '/message/create'
            payload = {
                'target_id': str(kook_event.get('target_id') or message_source.chat_id),
                'content': content,
                'type': msg_type,
            }
        else:
            endpoint = '/direct-message/create'
            extra = kook_event.get('extra') or {}
            payload = {
                'content': content,
                'type': msg_type,
            }
            if extra.get('code'):
                payload['chat_code'] = extra['code']
            else:
                payload['target_id'] = str(kook_event.get('author_id') or message_source.chat_id)

        if msg_id:
            payload['reply_msg_id'] = msg_id
            if quote_origin:
                payload['quote'] = msg_id

        raw = await self._request('POST', endpoint, json=payload)
        data = raw.get('data') or {}
        return platform_events.MessageResult(message_id=data.get('msg_id'), raw=raw)

    async def get_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> platform_events.MessageReceivedEvent:
        event = self._message_cache.get(str(message_id))
        if event is None:
            raise NotSupportedError('get_message:message_not_cached')
        return event

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        cached = self._group_cache.get(str(group_id))
        if cached:
            return cached
        raw = await self._request('GET', '/channel/view', params={'target_id': str(group_id)})
        data = raw.get('data') or {}
        return platform_entities.UserGroup(
            id=str(data.get('id') or group_id),
            name=str(data.get('name') or ''),
            member_count=data.get('user_count'),
        )

    async def get_group_list(self) -> list[platform_entities.UserGroup]:
        return list(self._group_cache.values())

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        raise NotSupportedError('get_group_member_list')

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        user = self._user_cache.get(str(user_id))
        if user is None:
            raw = await self._request('GET', '/user/view', params={'user_id': str(user_id)})
            data = raw.get('data') or {}
            user = platform_entities.User(
                id=str(data.get('id') or user_id),
                nickname=str(data.get('nickname') or data.get('username') or ''),
                username=data.get('username'),
                avatar_url=data.get('avatar'),
                is_bot=bool(data.get('bot', False)),
            )
        return platform_entities.UserGroupMember(
            user=user,
            group_id=str(group_id),
            role=platform_entities.MemberRole.MEMBER,
            display_name=user.nickname,
        )

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        cached = self._user_cache.get(str(user_id))
        if cached:
            return cached
        raw = await self._request('GET', '/user/view', params={'user_id': str(user_id)})
        data = raw.get('data') or {}
        return platform_entities.User(
            id=str(data.get('id') or user_id),
            nickname=str(data.get('nickname') or data.get('username') or ''),
            username=data.get('username'),
            avatar_url=data.get('avatar'),
            is_bot=bool(data.get('bot', False)),
        )

    async def get_friend_list(self) -> list[platform_entities.User]:
        return list(self._user_cache.values())

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        data = {'file': file_data}
        raw = await self._request('POST', '/asset/create', data=data, filename=filename)
        result = raw.get('data') or {}
        return str(result.get('url') or result.get('id') or '')

    async def get_file_url(self, file_id: str) -> str:
        return file_id

    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: platform_message.MessageChain,
    ) -> None:
        raise NotSupportedError('edit_message')

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        endpoint = '/message/delete' if str(chat_type).lower() in {'group', 'channel'} else '/direct-message/delete'
        await self._request('POST', endpoint, json={'msg_id': str(message_id)})

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        cached = self._message_cache.get(str(message_id))
        if cached is None:
            raise NotSupportedError('forward_message:message_not_cached')
        return await self.send_message(to_chat_type, str(to_chat_id), cached.message_chain)

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        raise NotSupportedError('mute_member')

    async def unmute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        raise NotSupportedError('unmute_member')

    async def kick_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        raise NotSupportedError('kick_member')

    async def leave_group(self, group_id: typing.Union[int, str]) -> None:
        raise NotSupportedError('leave_group')
