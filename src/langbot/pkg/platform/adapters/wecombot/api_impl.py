from __future__ import annotations

from langbot.pkg.telemetry import diagnostics

import typing

from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class WecomBotAPIMixin:
    _message_cache: dict[str, platform_events.MessageReceivedEvent]
    _user_cache: dict[str, platform_entities.User]
    _group_cache: dict[str, platform_entities.UserGroup]
    _member_cache: dict[tuple[str, str], platform_entities.UserGroupMember]

    @diagnostics.observe('api', 'get_message', source='platform', stage='accepted')
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

    @diagnostics.observe('api', 'get_user_info', source='platform', stage='accepted')
    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        cached = self._user_cache.get(str(user_id))
        if cached is None:
            raise NotSupportedError('get_user_info:not_cached')
        return cached

    @diagnostics.observe('api', 'get_friend_list', source='platform', stage='accepted')
    async def get_friend_list(self) -> list[platform_entities.User]:
        return list(self._user_cache.values())

    @diagnostics.observe('api', 'get_group_info', source='platform', stage='accepted')
    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        cached = self._group_cache.get(str(group_id))
        if cached is None:
            raise NotSupportedError('get_group_info:not_cached')
        return cached

    @diagnostics.observe('api', 'get_group_member_info', source='platform', stage='accepted')
    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        cached = self._member_cache.get((str(group_id), str(user_id)))
        if cached is None:
            raise NotSupportedError('get_group_member_info:not_cached')
        return cached

    @diagnostics.observe('api', 'get_group_member_list', source='platform', stage='accepted')
    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        return [
            member for (cached_group_id, _), member in self._member_cache.items() if cached_group_id == str(group_id)
        ]

    @diagnostics.observe('api', 'upload_file', source='platform', stage='accepted')
    async def upload_file(self, file_data: bytes, filename: str) -> str:
        raise NotSupportedError('upload_file')

    @diagnostics.observe('api', 'get_file_url', source='platform', stage='accepted')
    async def get_file_url(self, file_id: str) -> str:
        raise NotSupportedError('get_file_url')

    @diagnostics.observe('api', 'edit_message', source='platform', stage='accepted')
    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: platform_message.MessageChain,
    ) -> None:
        raise NotSupportedError('edit_message')

    @diagnostics.observe('api', 'delete_message', source='platform', stage='accepted')
    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        raise NotSupportedError('delete_message')

    @diagnostics.observe('api', 'forward_message', source='platform', stage='accepted')
    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        raise NotSupportedError('forward_message')

    @diagnostics.observe('api', 'mute_member', source='platform', stage='accepted')
    async def mute_member(self, group_id: typing.Union[int, str], user_id: typing.Union[int, str], duration: int = 0):
        raise NotSupportedError('mute_member')

    @diagnostics.observe('api', 'unmute_member', source='platform', stage='accepted')
    async def unmute_member(self, group_id: typing.Union[int, str], user_id: typing.Union[int, str]):
        raise NotSupportedError('unmute_member')

    @diagnostics.observe('api', 'kick_member', source='platform', stage='accepted')
    async def kick_member(self, group_id: typing.Union[int, str], user_id: typing.Union[int, str]):
        raise NotSupportedError('kick_member')

    @diagnostics.observe('api', 'leave_group', source='platform', stage='accepted')
    async def leave_group(self, group_id: typing.Union[int, str]):
        raise NotSupportedError('leave_group')
