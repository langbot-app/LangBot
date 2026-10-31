from __future__ import annotations

import typing

from langbot.libs.wecom_api.api import WecomClient
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class WecomAPIMixin:
    bot: WecomClient
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
        cached = self._user_cache.get(str(user_id))
        if cached is not None:
            return cached
        info = await self.bot.get_user_info(str(user_id))
        return platform_entities.User(
            id=info.get('userid') or user_id,
            nickname=info.get('name') or str(user_id),
            username=info.get('alias') or info.get('userid') or None,
        )

    async def get_friend_list(self) -> list[platform_entities.User]:
        return list(self._user_cache.values())

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        raise NotSupportedError('upload_file')

    async def get_file_url(self, file_id: str) -> str:
        raise NotSupportedError('get_file_url')

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        raise NotSupportedError('get_group_info')

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
