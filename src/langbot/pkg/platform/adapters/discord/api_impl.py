from __future__ import annotations

import datetime
import typing

import discord

from langbot.pkg.platform.adapters.discord.event_converter import DiscordEventConverter
from langbot.pkg.platform.adapters.discord.message_converter import DiscordMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DiscordAPIMixin:
    bot: discord.Client

    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: platform_message.MessageChain,
    ) -> None:
        channel = await self._get_channel(chat_id)
        message = await channel.fetch_message(int(message_id))
        content, files = await DiscordMessageConverter.yiri2target(new_content)
        if files:
            await message.edit(content=content, attachments=[])
            await channel.send(content=content, files=files)
            return
        await message.edit(content=content)

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        channel = await self._get_channel(chat_id)
        message = await channel.fetch_message(int(message_id))
        await message.delete()

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        from_channel = await self._get_channel(from_chat_id)
        to_channel = await self._get_channel(to_chat_id)
        message = await from_channel.fetch_message(int(message_id))
        files = [await attachment.to_file() for attachment in message.attachments]
        sent = await to_channel.send(content=message.content, files=files)
        return platform_events.MessageResult(message_id=sent.id, raw={'message_id': sent.id})

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        guild = await self._get_guild(group_id)
        return DiscordEventConverter.group_from_guild(guild)

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        guild = await self._get_guild(group_id)
        members = guild.members or [member async for member in guild.fetch_members(limit=None)]
        return [self._member_to_entity(member) for member in members]

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        guild = await self._get_guild(group_id)
        member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
        return self._member_to_entity(member)

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        user = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(int(user_id))
        return DiscordEventConverter.user_from_author(user)

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError

        raise NotSupportedError('upload_file')

    async def get_file_url(self, file_id: str) -> str:
        return file_id

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        guild = await self._get_guild(group_id)
        member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
        until = None
        if duration > 0:
            until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=duration)
        await member.timeout(until, reason='LangBot EBA mute_member')

    async def unmute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        guild = await self._get_guild(group_id)
        member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
        await member.timeout(None, reason='LangBot EBA unmute_member')

    async def kick_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        guild = await self._get_guild(group_id)
        member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
        await member.kick(reason='LangBot EBA kick_member')

    async def leave_group(self, group_id: typing.Union[int, str]) -> None:
        guild = await self._get_guild(group_id)
        await guild.leave()

    async def _get_channel(self, channel_id: typing.Union[int, str]) -> discord.abc.Messageable:
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            channel = await self.bot.fetch_channel(int(channel_id))
        return channel

    async def _get_guild(self, guild_id: typing.Union[int, str]) -> discord.Guild:
        guild = self.bot.get_guild(int(guild_id))
        if guild is None:
            guild = await self.bot.fetch_guild(int(guild_id))
        return guild

    @staticmethod
    def _member_to_entity(member: discord.Member) -> platform_entities.UserGroupMember:
        role = platform_entities.MemberRole.MEMBER
        if member.guild.owner_id == member.id:
            role = platform_entities.MemberRole.OWNER
        elif member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            role = platform_entities.MemberRole.ADMIN
        return platform_entities.UserGroupMember(
            user=DiscordEventConverter.user_from_author(member),
            group_id=member.guild.id,
            role=role,
            display_name=member.display_name,
            joined_at=member.joined_at.timestamp() if member.joined_at else None,
            title=member.top_role.name if member.top_role else None,
        )
