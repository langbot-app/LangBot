from __future__ import annotations

import typing

import discord


async def get_channel(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    return {
        'id': channel.id,
        'name': getattr(channel, 'name', ''),
        'type': str(channel.type),
        'guild_id': getattr(getattr(channel, 'guild', None), 'id', None),
    }


async def get_guild(bot: discord.Client, params: dict) -> dict:
    guild = bot.get_guild(int(params['guild_id'])) or await bot.fetch_guild(int(params['guild_id']))
    return {'id': guild.id, 'name': guild.name, 'member_count': guild.member_count, 'owner_id': guild.owner_id}


async def get_guild_channels(bot: discord.Client, params: dict) -> dict:
    guild = bot.get_guild(int(params['guild_id'])) or await bot.fetch_guild(int(params['guild_id']))
    channels = guild.channels or await guild.fetch_channels()
    return {'channels': [{'id': channel.id, 'name': channel.name, 'type': str(channel.type)} for channel in channels]}


async def get_guild_roles(bot: discord.Client, params: dict) -> dict:
    guild = bot.get_guild(int(params['guild_id'])) or await bot.fetch_guild(int(params['guild_id']))
    return {'roles': [{'id': role.id, 'name': role.name, 'position': role.position} for role in guild.roles]}


async def create_invite(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    invite = await channel.create_invite(
        max_age=params.get('max_age', 0),
        max_uses=params.get('max_uses', 0),
        unique=params.get('unique', True),
        reason=params.get('reason', 'LangBot EBA create_invite'),
    )
    return {'url': invite.url, 'code': invite.code}


async def pin_message(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    message = await channel.fetch_message(int(params['message_id']))
    await message.pin(reason=params.get('reason', 'LangBot EBA pin_message'))
    return {'ok': True}


async def unpin_message(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    message = await channel.fetch_message(int(params['message_id']))
    await message.unpin(reason=params.get('reason', 'LangBot EBA unpin_message'))
    return {'ok': True}


async def add_reaction(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    message = await channel.fetch_message(int(params['message_id']))
    await message.add_reaction(params['emoji'])
    return {'ok': True}


async def remove_reaction(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    message = await channel.fetch_message(int(params['message_id']))
    user = (
        bot.user
        if 'user_id' not in params
        else bot.get_user(int(params['user_id'])) or await bot.fetch_user(int(params['user_id']))
    )
    await message.remove_reaction(params['emoji'], user)
    return {'ok': True}


async def send_typing(bot: discord.Client, params: dict) -> dict:
    channel = bot.get_channel(int(params['channel_id'])) or await bot.fetch_channel(int(params['channel_id']))
    async with channel.typing():
        return {'ok': True}


PLATFORM_API_MAP: dict[str, typing.Callable[[discord.Client, dict], typing.Awaitable[dict]]] = {
    'get_channel': get_channel,
    'get_guild': get_guild,
    'get_guild_channels': get_guild_channels,
    'get_guild_roles': get_guild_roles,
    'create_invite': create_invite,
    'pin_message': pin_message,
    'unpin_message': unpin_message,
    'add_reaction': add_reaction,
    'remove_reaction': remove_reaction,
    'typing': send_typing,
}
