from __future__ import annotations

import os
import time
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
from langbot.pkg.platform.adapters.discord.interaction import (
    interaction_delivery_capabilities,
    interaction_event_from_component,
    parse_interaction_custom_id,
    send_interaction,
)
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DiscordAdapter(DiscordAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: discord.Client = pydantic.Field(exclude=True)

    message_converter: DiscordMessageConverter = DiscordMessageConverter()
    event_converter: DiscordEventConverter = DiscordEventConverter()

    _stream_buffer: dict = pydantic.PrivateAttr(default_factory=dict)
    _STREAM_EDIT_INTERVAL: typing.ClassVar[int] = 8
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

            async def on_interaction(self: discord.Client, interaction: discord.Interaction):
                custom_id = (interaction.data or {}).get('custom_id') if isinstance(interaction.data, dict) else None
                try:
                    parsed = parse_interaction_custom_id(custom_id)
                except ValueError:
                    if not interaction.response.is_done():
                        await interaction.response.send_message('Invalid or expired action', ephemeral=True)
                    return
                if parsed is None:
                    return
                if not interaction.response.is_done():
                    await interaction.response.defer()
                try:
                    await adapter_self._dispatch_eba_event(interaction_event_from_component(interaction, parsed))
                    if interaction.message is not None:
                        await interaction.message.edit(view=None)
                except Exception:
                    await adapter_self.logger.error(f'Error in Discord interaction callback: {traceback.format_exc()}')

            async def on_message_edit(self: discord.Client, before: discord.Message, after: discord.Message):
                if after.author.bot:
                    return
                await adapter_self._dispatch_gateway_tuple(
                    'message_edit', (before, after), self.user.id if self.user else None
                )

            async def on_raw_message_edit(self: discord.Client, payload: discord.RawMessageUpdateEvent):
                # Cached edits are handled above. Ignore embed-only updates, which
                # Discord also emits after resolving previews.
                if payload.cached_message is not None or not {'content', 'attachments'} & payload.data.keys():
                    return
                if payload.data.get('author', {}).get('bot'):
                    return
                try:
                    channel = await adapter_self._get_channel(payload.channel_id)
                    after = await channel.fetch_message(payload.message_id)
                except discord.HTTPException:
                    await adapter_self.logger.warning('Unable to fetch edited Discord message')
                    return
                if not after.author.bot:
                    await adapter_self._dispatch_gateway_tuple(
                        'message_edit', (None, after), self.user.id if self.user else None
                    )

            async def on_raw_message_delete(self: discord.Client, payload: discord.RawMessageDeleteEvent):
                # Raw callbacks also fire for cached messages. Dispatch only once,
                # retaining the cached payload when Discord supplies one.
                cached = getattr(payload, 'cached_message', None)
                await adapter_self._dispatch_gateway_tuple(
                    'message_delete' if cached is not None else 'raw_message_delete',
                    cached if cached is not None else payload,
                    self.user.id if self.user else None,
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
            'interaction.request',
        ]

    def get_interaction_capabilities(self) -> dict[str, typing.Any]:
        return interaction_delivery_capabilities()

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        content, files = await self.message_converter.yiri2target(message)
        guild = self.bot.get_guild(int(target_id)) if target_type == 'group' else None
        if guild is not None:
            # Guild-level events have no originating channel. Use only the
            # server's explicitly configured system channel for their replies.
            channel = guild.system_channel
            if channel is None:
                raise ValueError('Discord guild has no system channel configured for event replies')
        else:
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
        if action == 'interaction.request':
            return await send_interaction(self, params)
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError

            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self.bot, params)

    def _prune_streams(self):
        now = time.time()
        for key, state in tuple(self._stream_buffer.items()):
            if now - state['updated_at'] > 1800:
                self._stream_buffer.pop(key, None)
        while len(self._stream_buffer) >= 100:
            self._stream_buffer.pop(next(iter(self._stream_buffer)), None)

    async def is_stream_output_supported(self) -> bool:
        return True

    async def create_message_card(self, message_id: str, event: platform_events.MessageEvent) -> bool:
        """Set up a stream context for progressive editing.

        The first non-empty reply_message_chunk will send the initial
        message; subsequent chunks edit it in place.
        """
        source = event.source_platform_object
        if not isinstance(source, discord.Message):
            return False
        self._prune_streams()
        self._stream_buffer[message_id] = {
            'channel': source.channel,
            'sent_message': None,  # discord.Message set on first send
            'last_content': '',
            'chunk_count': 0,
            'updated_at': time.time(),
        }
        return True

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: typing.Any,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        msg_id = (
            bot_message.get('resp_message_id')
            if isinstance(bot_message, dict)
            else getattr(bot_message, 'resp_message_id', None)
        )

        tool_calls = (
            bot_message.get('tool_calls') if isinstance(bot_message, dict) else getattr(bot_message, 'tool_calls', None)
        )
        terminal = is_final and not tool_calls
        chunk_text = '\n\n'.join(m.text for m in message if isinstance(m, platform_message.Plain) and m.text)
        ctx = self._stream_buffer.get(msg_id) if msg_id else None
        if ctx is None:
            if terminal and message:
                await self.reply_message(message_source, message, quote_origin)
            return

        ctx['updated_at'] = time.time()
        ctx['chunk_count'] += 1
        if chunk_text:
            ctx['last_content'] = chunk_text

        try:
            content = ctx['last_content']
            sent = ctx['sent_message']
            if content:
                # Discord limits each message to 2000 characters. Keep the first
                # message as the live preview and deliver the remainder at completion.
                preview = content[:2000]
                if sent is None:
                    sent = await ctx['channel'].send(preview)
                    ctx['sent_message'] = sent
                elif is_final or ctx['chunk_count'] % self._STREAM_EDIT_INTERVAL == 0:
                    if preview != sent.content:
                        try:
                            ctx['sent_message'] = await sent.edit(content=preview)
                        except discord.NotFound:
                            ctx['sent_message'] = await ctx['channel'].send(preview)
                if terminal:
                    for offset in range(2000, len(content), 2000):
                        await ctx['channel'].send(content[offset : offset + 2000])
            if terminal:
                attachments = platform_message.MessageChain(
                    [
                        part
                        for part in message
                        if isinstance(part, (platform_message.Image, platform_message.File, platform_message.Voice))
                    ]
                )
                if attachments:
                    await self.reply_message(message_source, attachments, quote_origin)
        finally:
            # Tool-call completions are intermediate rounds, not the end of a reply.
            if terminal:
                self._stream_buffer.pop(msg_id, None)

    async def run_async(self):
        await self.bot.start(self.config['token'], reconnect=True)

    async def kill(self) -> bool:
        self._stream_buffer.clear()
        await self.bot.close()
        return True
