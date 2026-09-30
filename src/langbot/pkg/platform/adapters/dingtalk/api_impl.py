from __future__ import annotations

import typing

from langbot.libs.dingtalk_api.api import DingTalkClient
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class DingTalkAPIMixin:
    bot: DingTalkClient
    _message_cache: dict[str, platform_events.MessageReceivedEvent]
    _user_cache: dict[str, platform_entities.User]
    _group_cache: dict[str, platform_entities.UserGroup]

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
        return self._group_cache.get(str(group_id)) or platform_entities.UserGroup(id=group_id, name='')

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
            raise NotSupportedError('get_group_member_info:user_not_cached')
        return platform_entities.UserGroupMember(
            user=user,
            group_id=group_id,
            role=platform_entities.MemberRole.MEMBER,
            display_name=user.nickname,
        )

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        return self._user_cache.get(str(user_id)) or platform_entities.User(id=user_id, nickname='')

    async def get_friend_list(self) -> list[platform_entities.User]:
        return list(self._user_cache.values())

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        raise NotSupportedError('upload_file')

    async def get_file_url(self, file_id: str) -> str:
        return await self.bot.get_file_url(file_id)
