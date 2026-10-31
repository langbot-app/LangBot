from __future__ import annotations

import typing

from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot.pkg.platform.adapters.officialaccount.errors import NotSupportedError


class OfficialAccountAPIMixin:
    _message_cache: dict[str, platform_events.MessageReceivedEvent]
    _user_cache: dict[str, platform_entities.User]

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

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        user = self._user_cache.get(str(user_id))
        if user is None:
            raise NotSupportedError('get_user_info:not_cached')
        return user

    async def get_friend_list(self) -> list[platform_entities.User]:
        return list(self._user_cache.values())

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
        raise NotSupportedError('delete_message')

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        raise NotSupportedError('forward_message')

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        raise NotSupportedError('upload_file')

    async def get_file_url(self, file_id: str) -> str:
        raise NotSupportedError('get_file_url')

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        raise NotSupportedError('get_group_info')

    async def get_group_list(self) -> list[platform_entities.UserGroup]:
        raise NotSupportedError('get_group_list')

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
        raise NotSupportedError('get_group_member_info')
