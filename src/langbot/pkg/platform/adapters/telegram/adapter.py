"""Telegram adapter main class (EBA version).

Inherits AbstractPlatformAdapter, integrating all modules.
Preserves all existing functionality (messaging, streaming output, markdown card, forum topics, etc.).
"""

from __future__ import annotations

import time
import typing
import traceback

import telegram
import telegram.ext
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import telegramify_markdown
import pydantic

from langbot.pkg.utils import httpclient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger

from langbot.pkg.platform.adapters.telegram.message_converter import TelegramMessageConverter
from langbot.pkg.platform.adapters.telegram.event_converter import TelegramEventConverter, LegacyEventConverter
from langbot.pkg.platform.adapters.telegram.api_impl import TelegramAPIMixin
from langbot.pkg.platform.adapters.telegram.platform_api import PLATFORM_API_MAP


class TelegramAdapter(TelegramAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    """Telegram adapter (EBA version)."""

    bot: telegram.Bot = pydantic.Field(exclude=True)
    application: telegram.ext.Application = pydantic.Field(exclude=True)

    message_converter: TelegramMessageConverter = TelegramMessageConverter()
    event_converter: TelegramEventConverter = TelegramEventConverter()
    legacy_event_converter: LegacyEventConverter = LegacyEventConverter()

    config: dict

    msg_stream_id: dict
    """Stream message ID map. Key: stream message ID, value: first message source ID."""

    seq: int
    """Sequence number for message ordering."""

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        async def telegram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.message and not update.edited_message and not update.chat_member \
                    and not update.my_chat_member and not update.callback_query and not update.message_reaction:
                return

            # Skip messages from the bot itself
            if update.message and update.message.from_user and update.message.from_user.is_bot:
                return

            try:
                # Legacy event type callbacks (compat with existing botmgr FriendMessage / GroupMessage listeners)
                if update.message and (platform_events.FriendMessage in self.listeners
                                       or platform_events.GroupMessage in self.listeners):
                    legacy_event = await self.legacy_event_converter.target2yiri(update, self.bot, self.bot_account_id)
                    if legacy_event and type(legacy_event) in self.listeners:
                        await self.listeners[type(legacy_event)](legacy_event, self)

                # EBA wildcard event callback (Event base class registered as wildcard)
                if platform_events.Event in self.listeners:
                    eba_event = await self.event_converter.target2yiri(update, self.bot, self.bot_account_id)
                    if eba_event:
                        await self.listeners[platform_events.Event](eba_event, self)

                # EBA specific event type callback
                if platform_events.EBAEvent in self.listeners:
                    eba_event = await self.event_converter.target2yiri(update, self.bot, self.bot_account_id)
                    if eba_event:
                        await self.listeners[platform_events.EBAEvent](eba_event, self)

            except Exception:
                await self.logger.error(f'Error in telegram callback: {traceback.format_exc()}')

        application = ApplicationBuilder().token(config['token']).build()
        bot = application.bot

        # Register handler for all common update types
        application.add_handler(
            MessageHandler(
                filters.TEXT | (filters.COMMAND) | filters.PHOTO | filters.VOICE | filters.Document.ALL,
                telegram_callback,
            )
        )
        # Register edited message handler
        application.add_handler(
            MessageHandler(
                filters.UpdateType.EDITED_MESSAGE,
                telegram_callback,
            )
        )

        super().__init__(
            config=config,
            logger=logger,
            msg_stream_id={},
            seq=1,
            bot=bot,
            application=application,
            bot_account_id='',
            listeners={},
        )

    # ---- Capability Declaration ----

    def get_supported_events(self) -> list[str]:
        return [
            "message.received",
            "message.edited",
            "message.deleted",
            "message.reaction",
            "group.member_joined",
            "group.member_left",
            "group.member_banned",
            "group.info_updated",
            "bot.invited_to_group",
            "bot.removed_from_group",
        ]

    def get_supported_apis(self) -> list[str]:
        return [
            "send_message",
            "reply_message",
            "edit_message",
            "delete_message",
            "forward_message",
            "get_group_info",
            "get_group_member_list",
            "get_group_member_info",
            "get_user_info",
            "get_file_url",
            "mute_member",
            "unmute_member",
            "kick_member",
            "leave_group",
            "call_platform_api",
        ]

    # ---- Message Send / Reply (preserving original logic) ----

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        components = await TelegramMessageConverter.yiri2target(message, self.bot)

        chat_id_str, _, thread_id_str = str(target_id).partition('#')
        chat_id: int | str = int(chat_id_str) if chat_id_str.lstrip('-').isdigit() else chat_id_str
        message_thread_id = int(thread_id_str) if thread_id_str and thread_id_str.isdigit() else None

        for component in components:
            component_type = component.get('type')
            args = {'chat_id': chat_id}
            if message_thread_id is not None:
                args['message_thread_id'] = message_thread_id

            if component_type == 'text':
                text = component.get('text', '')
                if self.config['markdown_card'] is True:
                    text = telegramify_markdown.markdownify(content=text)
                    args['parse_mode'] = 'MarkdownV2'
                args['text'] = text
                await self.bot.send_message(**args)
            elif component_type == 'photo':
                photo = component.get('photo')
                if photo is None:
                    continue
                args['photo'] = telegram.InputFile(photo)
                await self.bot.send_photo(**args)
            elif component_type == 'document':
                doc = component.get('document')
                if doc is None:
                    continue
                filename = component.get('filename', 'file')
                args['document'] = telegram.InputFile(doc, filename=filename)
                await self.bot.send_document(**args)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        assert isinstance(message_source.source_platform_object, Update)
        components = await TelegramMessageConverter.yiri2target(message, self.bot)

        for component in components:
            if component['type'] == 'text':
                if self.config['markdown_card'] is True:
                    content = telegramify_markdown.markdownify(
                        content=component['text'],
                    )
                else:
                    content = component['text']
                args = {
                    'chat_id': message_source.source_platform_object.effective_chat.id,
                    'text': content,
                }
                if self.config['markdown_card'] is True:
                    args['parse_mode'] = 'MarkdownV2'

        if message_source.source_platform_object.message.message_thread_id:
            args['message_thread_id'] = message_source.source_platform_object.message.message_thread_id

        if quote_origin:
            args['reply_to_message_id'] = message_source.source_platform_object.message.id

        await self.bot.send_message(**args)

    # ---- Streaming Output (preserving original logic) ----

    def _process_markdown(self, text: str) -> str:
        if self.config.get('markdown_card', False):
            return telegramify_markdown.markdownify(content=text)
        return text

    def _build_message_args(self, chat_id: int, text: str, message_thread_id: int = None, **extra_args) -> dict:
        args = {'chat_id': chat_id, 'text': self._process_markdown(text), **extra_args}
        if message_thread_id:
            args['message_thread_id'] = message_thread_id
        if self.config.get('markdown_card', False):
            args['parse_mode'] = 'MarkdownV2'
        return args

    async def create_message_card(self, message_id, event):
        assert isinstance(event.source_platform_object, Update)
        update = event.source_platform_object
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        message_thread_id = update.message.message_thread_id

        if chat_type == 'private':
            draft_id = int(time.time() * 1000)
            self.msg_stream_id[message_id] = ('private', draft_id)

            args = self._build_message_args(chat_id, 'Thinking...', message_thread_id, draft_id=draft_id)
            await self.bot.send_message_draft(**args)
        else:
            args = self._build_message_args(chat_id, 'Thinking...', message_thread_id)
            send_msg = await self.bot.send_message(**args)
            self.msg_stream_id[message_id] = ('group', send_msg.message_id)

        return True

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence
        assert isinstance(message_source.source_platform_object, Update)
        update = message_source.source_platform_object
        chat_id = update.effective_chat.id
        message_thread_id = update.message.message_thread_id

        if message_id not in self.msg_stream_id:
            return

        chat_mode, draft_id = self.msg_stream_id[message_id]
        components = await TelegramMessageConverter.yiri2target(message, self.bot)

        if not components or components[0]['type'] != 'text':
            if is_final and bot_message.tool_calls is None:
                self.msg_stream_id.pop(message_id)
            return

        content = components[0]['text']

        if chat_mode == 'private':
            args = self._build_message_args(chat_id, content, message_thread_id, draft_id=draft_id)
            await self.bot.send_message_draft(**args)
            if is_final and bot_message.tool_calls is None:
                del args['draft_id']
                await self.bot.send_message(**args)
                self.msg_stream_id.pop(message_id)
        else:
            stream_id = draft_id
            if (msg_seq - 1) % 8 == 0 or is_final:
                args = {
                    'message_id': stream_id,
                    'chat_id': chat_id,
                    'text': self._process_markdown(content),
                }
                if self.config.get('markdown_card', False):
                    args['parse_mode'] = 'MarkdownV2'
                await self.bot.edit_message_text(**args)

            if is_final and bot_message.tool_calls is None:
                self.msg_stream_id.pop(message_id)

    # ---- Forum Topic / Custom launcher_id (preserving original logic) ----

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str | None:
        if not isinstance(event.source_platform_object, Update):
            return None

        message = event.source_platform_object.message
        if not message:
            return None

        if message.message_thread_id:
            if isinstance(event, platform_events.GroupMessage):
                return f'{event.group.id}#{message.message_thread_id}'
            elif isinstance(event, platform_events.FriendMessage):
                return f'{event.sender.id}#{message.message_thread_id}'

        return None

    # ---- Stream Output Support Check ----

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def is_muted(self, group_id: int) -> bool:
        return False

    # ---- Event Listeners ----

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

    # ---- Pass-through API ----

    async def call_platform_api(
        self,
        action: str,
        params: dict = {},
    ) -> dict:
        """Call a Telegram-specific platform API."""
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError
            raise NotSupportedError(f"call_platform_api:{action}")
        return await handler(self.bot, params)

    # ---- Lifecycle ----

    async def run_async(self):
        await self.application.initialize()
        self.bot_account_id = (await self.bot.get_me()).username
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await self.application.start()
        await self.logger.info('Telegram adapter running')

    async def kill(self) -> bool:
        if self.application.running:
            await self.application.stop()
            if self.application.updater:
                await self.application.updater.stop()
            await self.logger.info('Telegram adapter stopped')
        return True
