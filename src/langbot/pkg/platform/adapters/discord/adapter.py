from __future__ import annotations

import os
import traceback
import typing

import discord
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.adapters.discord.api_impl import DiscordAPIMixin
from langbot.pkg.platform.adapters.discord.event_converter import DiscordEventConverter
from langbot.pkg.platform.adapters.discord.message_converter import DiscordMessageConverter
from langbot.pkg.platform.adapters.discord.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DiscordAdapter(DiscordAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: discord.Client = pydantic.Field(exclude=True)

    message_converter: DiscordMessageConverter = DiscordMessageConverter()
    event_converter: DiscordEventConverter = DiscordEventConverter()

    config: dict
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        adapter_self = self

        class LangBotDiscordClient(discord.Client):
            async def on_ready(self: discord.Client):
                adapter_self.bot_account_id = str(self.user.id) if self.user else ''
                await adapter_self.logger.info(f'Discord adapter running as {self.user}')

            async def on_message(self: discord.Client, message: discord.Message):
                if self.user and message.author.id == self.user.id:
                    return
                if message.author.bot:
                    return
                try:
                    if (
                        platform_events.FriendMessage in adapter_self.listeners
                        or platform_events.GroupMessage in adapter_self.listeners
                    ):
                        legacy_event = await adapter_self.event_converter.target2legacy(message)
                        callback = adapter_self.listeners.get(type(legacy_event))
                        if callback:
                            await callback(legacy_event, adapter_self)

                    eba_event = await adapter_self.event_converter.target2yiri(
                        message, self.user.id if self.user else None
                    )
                    if eba_event:
                        await adapter_self._dispatch_eba_event(eba_event)
                except Exception:
                    await adapter_self.logger.error(f'Error in discord on_message: {traceback.format_exc()}')

            async def on_message_edit(self: discord.Client, before: discord.Message, after: discord.Message):
                await adapter_self._dispatch_gateway_tuple(
                    'message_edit', (before, after), self.user.id if self.user else None
                )

            async def on_message_delete(self: discord.Client, message: discord.Message):
                await adapter_self._dispatch_gateway_tuple(
                    'message_delete', message, self.user.id if self.user else None
                )

            async def on_raw_message_delete(self: discord.Client, payload: discord.RawMessageDeleteEvent):
                await adapter_self._dispatch_gateway_tuple(
                    'raw_message_delete',
                    payload,
                    self.user.id if self.user else None,
                )

            async def on_reaction_add(
                self: discord.Client, reaction: discord.Reaction, user: discord.User | discord.Member
            ):
                if self.user and user.id == self.user.id:
                    return
                await adapter_self._dispatch_gateway_tuple(
                    'reaction_add', (reaction, user), self.user.id if self.user else None
                )

            async def on_reaction_remove(
                self: discord.Client, reaction: discord.Reaction, user: discord.User | discord.Member
            ):
                if self.user and user.id == self.user.id:
                    return
                await adapter_self._dispatch_gateway_tuple(
                    'reaction_remove', (reaction, user), self.user.id if self.user else None
                )

            async def on_raw_reaction_add(self: discord.Client, payload: discord.RawReactionActionEvent):
                if self.user and payload.user_id == self.user.id:
                    return
                await adapter_self._dispatch_gateway_tuple(
                    'raw_reaction_add',
                    payload,
                    self.user.id if self.user else None,
                )

            async def on_raw_reaction_remove(self: discord.Client, payload: discord.RawReactionActionEvent):
                if self.user and payload.user_id == self.user.id:
                    return
                await adapter_self._dispatch_gateway_tuple(
                    'raw_reaction_remove',
                    payload,
                    self.user.id if self.user else None,
                )

            async def on_member_join(self: discord.Client, member: discord.Member):
                await adapter_self._dispatch_gateway_tuple('member_join', member, self.user.id if self.user else None)

            async def on_member_remove(self: discord.Client, member: discord.Member):
                await adapter_self._dispatch_gateway_tuple('member_remove', member, self.user.id if self.user else None)

            async def on_guild_join(self: discord.Client, guild: discord.Guild):
                await adapter_self._dispatch_gateway_tuple('guild_join', guild, self.user.id if self.user else None)

            async def on_guild_remove(self: discord.Client, guild: discord.Guild):
                await adapter_self._dispatch_gateway_tuple('guild_remove', guild, self.user.id if self.user else None)

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.reactions = True

        args = {}
        if os.getenv('http_proxy'):
            args['proxy'] = os.getenv('http_proxy')
        bot = LangBotDiscordClient(intents=intents, **args)

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=config.get('client_id', ''),
            listeners={},
            bot=bot,
        )

    def get_supported_events(self) -> list[str]:
        return [
            'message.received',
            'message.edited',
            'message.deleted',
            'message.reaction',
            'group.member_joined',
            'group.member_left',
            'bot.invited_to_group',
            'bot.removed_from_group',
            'platform.specific',
        ]

    def get_supported_apis(self) -> list[str]:
        return [
            'send_message',
            'reply_message',
            'edit_message',
            'delete_message',
            'forward_message',
            'get_group_info',
            'get_group_member_list',
            'get_group_member_info',
            'get_user_info',
            'get_file_url',
            'mute_member',
            'unmute_member',
            'kick_member',
            'leave_group',
            'call_platform_api',
        ]

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        content, files = await self.message_converter.yiri2target(message)
        channel = await self._get_channel(target_id)
        kwargs = {'content': content}
        if files:
            kwargs['files'] = files
        sent = await channel.send(**kwargs)
        return platform_events.MessageResult(message_id=sent.id, raw={'message_id': sent.id})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        assert isinstance(message_source.source_platform_object, discord.Message)
        content, files = await self.message_converter.yiri2target(message)
        kwargs = {'content': content}
        if files:
            kwargs['files'] = files
        if quote_origin:
            kwargs['reference'] = message_source.source_platform_object
            kwargs['mention_author'] = any(isinstance(component, platform_message.At) for component in message.root)
        sent = await message_source.source_platform_object.channel.send(**kwargs)
        return platform_events.MessageResult(message_id=sent.id, raw={'message_id': sent.id})

    async def _dispatch_gateway_tuple(self, kind: str, payload, bot_user_id: int | None):
        try:
            event = await self.event_converter.target2yiri((kind, payload), bot_user_id)
            if event:
                await self._dispatch_eba_event(event)
        except Exception:
            await self.logger.error(f'Error in discord {kind}: {traceback.format_exc()}')

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners.pop(event_type, None)

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError

            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self.bot, params)

    async def run_async(self):
        await self.bot.start(self.config['token'], reconnect=True)

    async def kill(self) -> bool:
        await self.bot.close()
        return True
