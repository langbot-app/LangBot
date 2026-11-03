from __future__ import annotations

import typing

from langbot.pkg.platform.adapters.line.errors import NotSupportedError
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class LineAPIMixin:
    """Optional universal APIs; LINE only exposes profile and group summaries."""

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        import asyncio

        profile = await asyncio.to_thread(self.bot.get_profile, str(user_id))
        return platform_entities.User(
            id=profile.user_id,
            nickname=profile.display_name,
            avatar_url=profile.picture_url or '',
        )

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        import asyncio

        try:
            summary = await asyncio.to_thread(self.bot.get_group_summary, str(group_id))
        except Exception as exc:
            raise NotSupportedError('get_group_info:group_not_found') from exc
        return platform_entities.UserGroup(
            id=summary.group_id,
            name=summary.group_name,
            avatar_url=summary.picture_url or '',
        )

    async def leave_group(self, group_id: typing.Union[int, str]) -> None:
        import asyncio

        await asyncio.to_thread(self.bot.leave_group, str(group_id))

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        # LINE does not expose a group member listing API.
        raise NotSupportedError('get_group_member_list')

    async def get_group_list(self) -> list[platform_entities.UserGroup]:
        raise NotSupportedError('get_group_list')

    async def get_friend_list(self) -> list[platform_entities.User]:
        raise NotSupportedError('get_friend_list')

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
