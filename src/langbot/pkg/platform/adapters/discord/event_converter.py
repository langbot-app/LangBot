from __future__ import annotations

import typing

import discord

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.discord.message_converter import DiscordMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class DiscordEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> discord.Message:
        raise NotImplementedError

    @staticmethod
    async def target2yiri(event: typing.Any, bot_user_id: int | None = None) -> platform_events.Event | None:
        if isinstance(event, discord.Message):
            return await DiscordEventConverter.message_to_eba(event)
        if isinstance(event, tuple) and len(event) == 2:
            kind, payload = event
            if kind == 'message_edit':
                before, after = payload
                return await DiscordEventConverter.message_edit_to_eba(before, after)
            if kind == 'message_delete':
                return await DiscordEventConverter.message_delete_to_eba(payload)
            if kind == 'raw_message_delete':
                return DiscordEventConverter.raw_message_delete_to_eba(payload)
            if kind == 'reaction_add':
                reaction, user = payload
                return DiscordEventConverter.reaction_to_eba(reaction, user, True)
            if kind == 'reaction_remove':
                reaction, user = payload
                return DiscordEventConverter.reaction_to_eba(reaction, user, False)
            if kind == 'raw_reaction_add':
                return DiscordEventConverter.raw_reaction_to_eba(payload, True)
            if kind == 'raw_reaction_remove':
                return DiscordEventConverter.raw_reaction_to_eba(payload, False)
            if kind == 'member_join':
                return DiscordEventConverter.member_join_to_eba(payload, bot_user_id)
            if kind == 'member_remove':
                return DiscordEventConverter.member_left_to_eba(payload, bot_user_id)
            if kind == 'guild_join':
                return DiscordEventConverter.guild_join_to_eba(payload)
            if kind == 'guild_remove':
                return DiscordEventConverter.guild_remove_to_eba(payload)
        return None

    @staticmethod
    async def message_to_eba(message: discord.Message) -> platform_events.MessageReceivedEvent:
        message_chain = await DiscordMessageConverter.target2yiri(message)
        group = DiscordEventConverter.group_from_message(message)
        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name='discord',
            message_id=message.id,
            message_chain=message_chain,
            sender=DiscordEventConverter.user_from_author(message.author),
            chat_type=platform_entities.ChatType.PRIVATE
            if isinstance(message.channel, discord.DMChannel)
            else platform_entities.ChatType.GROUP,
            chat_id=message.channel.id,
            group=group,
            timestamp=message.created_at.timestamp(),
            source_platform_object=message,
        )

    @staticmethod
    async def message_edit_to_eba(
        before: discord.Message, after: discord.Message
    ) -> platform_events.MessageEditedEvent:
        return platform_events.MessageEditedEvent(
            type='message.edited',
            adapter_name='discord',
            message_id=after.id,
            new_content=await DiscordMessageConverter.target2yiri(after),
            editor=DiscordEventConverter.user_from_author(after.author),
            chat_type=platform_entities.ChatType.PRIVATE
            if isinstance(after.channel, discord.DMChannel)
            else platform_entities.ChatType.GROUP,
            chat_id=after.channel.id,
            group=DiscordEventConverter.group_from_message(after),
            timestamp=after.edited_at.timestamp() if after.edited_at else after.created_at.timestamp(),
            source_platform_object=after,
        )

    @staticmethod
    async def message_delete_to_eba(message: discord.Message) -> platform_events.MessageDeletedEvent:
        return platform_events.MessageDeletedEvent(
            type='message.deleted',
            adapter_name='discord',
            message_id=message.id,
            operator=None,
            chat_type=platform_entities.ChatType.PRIVATE
            if isinstance(message.channel, discord.DMChannel)
            else platform_entities.ChatType.GROUP,
            chat_id=message.channel.id,
            group=DiscordEventConverter.group_from_message(message),
            timestamp=message.created_at.timestamp() if message.created_at else 0.0,
            source_platform_object=message,
        )

    @staticmethod
    def raw_message_delete_to_eba(payload: discord.RawMessageDeleteEvent) -> platform_events.MessageDeletedEvent:
        return platform_events.MessageDeletedEvent(
            type='message.deleted',
            adapter_name='discord',
            message_id=payload.message_id,
            operator=None,
            chat_type=platform_entities.ChatType.PRIVATE
            if payload.guild_id is None
            else platform_entities.ChatType.GROUP,
            chat_id=payload.channel_id,
            group=platform_entities.UserGroup(id=payload.guild_id) if payload.guild_id is not None else None,
            source_platform_object=payload,
        )

    @staticmethod
    def reaction_to_eba(
        reaction: discord.Reaction,
        user: discord.User | discord.Member,
        is_add: bool,
    ) -> platform_events.MessageReactionEvent:
        message = reaction.message
        return platform_events.MessageReactionEvent(
            type='message.reaction',
            adapter_name='discord',
            message_id=message.id,
            user=DiscordEventConverter.user_from_author(user),
            reaction=str(reaction.emoji),
            is_add=is_add,
            chat_type=platform_entities.ChatType.PRIVATE
            if isinstance(message.channel, discord.DMChannel)
            else platform_entities.ChatType.GROUP,
            chat_id=message.channel.id,
            group=DiscordEventConverter.group_from_message(message),
            source_platform_object=reaction,
        )

    @staticmethod
    def raw_reaction_to_eba(
        payload: discord.RawReactionActionEvent,
        is_add: bool,
    ) -> platform_events.MessageReactionEvent:
        member = getattr(payload, 'member', None)
        user = member or getattr(payload, 'user', None)
        if user is None:
            user = platform_entities.User(id=payload.user_id)
        else:
            user = DiscordEventConverter.user_from_author(user)
        return platform_events.MessageReactionEvent(
            type='message.reaction',
            adapter_name='discord',
            message_id=payload.message_id,
            user=user,
            reaction=str(payload.emoji),
            is_add=is_add,
            chat_type=platform_entities.ChatType.PRIVATE
            if payload.guild_id is None
            else platform_entities.ChatType.GROUP,
            chat_id=payload.channel_id,
            group=platform_entities.UserGroup(id=payload.guild_id) if payload.guild_id is not None else None,
            source_platform_object=payload,
        )

    @staticmethod
    def member_join_to_eba(
        member: discord.Member,
        bot_user_id: int | None,
    ) -> platform_events.BotInvitedToGroupEvent | platform_events.MemberJoinedEvent:
        group = DiscordEventConverter.group_from_guild(member.guild)
        user = DiscordEventConverter.user_from_author(member)
        if bot_user_id is not None and member.id == bot_user_id:
            return platform_events.BotInvitedToGroupEvent(
                type='bot.invited_to_group',
                adapter_name='discord',
                group=group,
                inviter=None,
                timestamp=member.joined_at.timestamp() if member.joined_at else 0.0,
                source_platform_object=member,
            )
        return platform_events.MemberJoinedEvent(
            type='group.member_joined',
            adapter_name='discord',
            group=group,
            member=user,
            inviter=None,
            join_type='direct',
            timestamp=member.joined_at.timestamp() if member.joined_at else 0.0,
            source_platform_object=member,
        )

    @staticmethod
    def member_left_to_eba(
        member: discord.Member,
        bot_user_id: int | None,
    ) -> platform_events.BotRemovedFromGroupEvent | platform_events.MemberLeftEvent:
        group = DiscordEventConverter.group_from_guild(member.guild)
        user = DiscordEventConverter.user_from_author(member)
        if bot_user_id is not None and member.id == bot_user_id:
            return platform_events.BotRemovedFromGroupEvent(
                type='bot.removed_from_group',
                adapter_name='discord',
                group=group,
                operator=None,
                source_platform_object=member,
            )
        return platform_events.MemberLeftEvent(
            type='group.member_left',
            adapter_name='discord',
            group=group,
            member=user,
            is_kicked=False,
            operator=None,
            source_platform_object=member,
        )

    @staticmethod
    def guild_join_to_eba(guild: discord.Guild) -> platform_events.BotInvitedToGroupEvent:
        return platform_events.BotInvitedToGroupEvent(
            type='bot.invited_to_group',
            adapter_name='discord',
            group=DiscordEventConverter.group_from_guild(guild),
            inviter=None,
            source_platform_object=guild,
        )

    @staticmethod
    def guild_remove_to_eba(guild: discord.Guild) -> platform_events.BotRemovedFromGroupEvent:
        return platform_events.BotRemovedFromGroupEvent(
            type='bot.removed_from_group',
            adapter_name='discord',
            group=DiscordEventConverter.group_from_guild(guild),
            operator=None,
            source_platform_object=guild,
        )

    @staticmethod
    async def target2legacy(message: discord.Message) -> platform_events.FriendMessage | platform_events.GroupMessage:
        message_chain = await DiscordMessageConverter.target2yiri(message)
        if isinstance(message.channel, discord.DMChannel):
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=message.author.id,
                    nickname=message.author.name,
                    remark=str(message.channel.id),
                ),
                message_chain=message_chain,
                time=message.created_at.timestamp(),
                source_platform_object=message,
            )
        return platform_events.GroupMessage(
            sender=platform_entities.GroupMember(
                id=message.author.id,
                member_name=message.author.display_name,
                permission=platform_entities.Permission.Member,
                group=platform_entities.Group(
                    id=message.channel.id,
                    name=message.channel.name,
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
            ),
            message_chain=message_chain,
            time=message.created_at.timestamp(),
            source_platform_object=message,
        )

    @staticmethod
    def user_from_author(author: discord.User | discord.Member) -> platform_entities.User:
        return platform_entities.User(
            id=author.id,
            nickname=getattr(author, 'display_name', None) or author.name,
            avatar_url=str(author.display_avatar.url) if getattr(author, 'display_avatar', None) else None,
            is_bot=author.bot,
            username=author.name,
        )

    @staticmethod
    def group_from_message(message: discord.Message) -> platform_entities.UserGroup | None:
        guild = getattr(message, 'guild', None)
        if guild is None:
            return None
        return DiscordEventConverter.group_from_guild(guild)

    @staticmethod
    def group_from_guild(guild: discord.Guild) -> platform_entities.UserGroup:
        return platform_entities.UserGroup(
            id=guild.id,
            name=guild.name,
            member_count=guild.member_count,
            avatar_url=str(guild.icon.url) if guild.icon else None,
            owner_id=guild.owner_id,
        )
