from __future__ import annotations


import telegram
import telegram.ext
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import telegramify_markdown
import typing
import traceback
import base64
import aiohttp
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class TelegramMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: telegram.Bot) -> list[dict]:
        components = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                components.append({'type': 'text', 'text': component.text})
            elif isinstance(component, platform_message.Image):
                photo_bytes = None

                if component.base64:
                    photo_bytes = base64.b64decode(component.base64)
                elif component.url:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(component.url) as response:
                            photo_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        photo_bytes = f.read()

                components.append({'type': 'photo', 'photo': photo_bytes})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    components.extend(await TelegramMessageConverter.yiri2target(node.message_chain, bot))

        return components

    @staticmethod
    async def target2yiri(message: telegram.Message, bot: telegram.Bot, bot_account_id: str):
        message_components = []

        def parse_message_text(text: str) -> list[platform_message.MessageComponent]:
            msg_components = []

            if f'@{bot_account_id}' in text:
                msg_components.append(platform_message.At(target=bot_account_id))
                text = text.replace(f'@{bot_account_id}', '')
            msg_components.append(platform_message.Plain(text=text))

            return msg_components

        if message.text:
            message_text = message.text
            message_components.extend(parse_message_text(message_text))

        if message.photo:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.photo[-1].get_file()

            file_bytes = None
            file_format = ''

            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(file.file_path) as response:
                    file_bytes = await response.read()
                    file_format = 'image/jpeg'

            message_components.append(
                platform_message.Image(
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}'
                )
            )

        return platform_message.MessageChain(message_components)


class TelegramEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent, bot: telegram.Bot):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: Update, bot: telegram.Bot, bot_account_id: str):
        lb_message = await TelegramMessageConverter.target2yiri(event.message, bot, bot_account_id)

        if event.effective_chat.type == 'private':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.effective_chat.id,
                    nickname=event.effective_chat.first_name,
                    remark=str(event.effective_chat.id),
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event,
            )
        elif event.effective_chat.type == 'group' or 'supergroup':
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.effective_chat.id,
                    member_name=event.effective_chat.title,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.effective_chat.id,
                        name=event.effective_chat.title,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event,
            )


class TelegramAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: telegram.Bot = pydantic.Field(exclude=True)
    application: telegram.ext.Application = pydantic.Field(exclude=True)

    message_converter: TelegramMessageConverter = TelegramMessageConverter()
    event_converter: TelegramEventConverter = TelegramEventConverter()

    config: dict

    msg_stream_id: dict  # 流式消息id字典，key为流式消息id，value为首次消息源id，用于在流式消息时判断编辑那条消息

    seq: int  # 消息中识别消息顺序，直接以seq作为标识

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        async def telegram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.message.from_user.is_bot:
                return

            try:
                lb_event = await self.event_converter.target2yiri(update, self.bot, self.bot_account_id)
                await self.listeners[type(lb_event)](lb_event, self)
                await self.is_stream_output_supported()
            except Exception:
                await self.logger.error(f'Error in telegram callback: {traceback.format_exc()}')

        application = ApplicationBuilder().token(config['token']).build()
        bot = application.bot
        application.add_handler(MessageHandler(filters.TEXT | (filters.COMMAND) | filters.PHOTO, telegram_callback))
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

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

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
        if quote_origin:
            args['reply_to_message_id'] = message_source.source_platform_object.message.id

        await self.bot.send_message(**args)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        msg_seq = bot_message.msg_sequence
        if (msg_seq - 1) % 8 == 0 or is_final:
            assert isinstance(message_source.source_platform_object, Update)
            components = await TelegramMessageConverter.yiri2target(message, self.bot)
            args = {}
            message_id = message_source.source_platform_object.message.id
            if quote_origin:
                args['reply_to_message_id'] = message_source.source_platform_object.message.id

            component = components[0]
            if message_id not in self.msg_stream_id:  # 当消息回复第一次时，发送新消息
                # time.sleep(0.6)
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

                send_msg = await self.bot.send_message(**args)
                send_msg_id = send_msg.message_id
                self.msg_stream_id[message_id] = send_msg_id
            else:  # 存在消息的时候直接编辑消息1
                if component['type'] == 'text':
                    if self.config['markdown_card'] is True:
                        content = telegramify_markdown.markdownify(
                            content=component['text'],
                        )
                    else:
                        content = component['text']
                    args = {
                        'message_id': self.msg_stream_id[message_id],
                        'chat_id': message_source.source_platform_object.effective_chat.id,
                        'text': content,
                    }
                    if self.config['markdown_card'] is True:
                        args['parse_mode'] = 'MarkdownV2'

                await self.bot.edit_message_text(**args)
            if is_final and bot_message.tool_calls is None:
                # self.seq = 1  # 消息回复结束之后重置seq
                self.msg_stream_id.pop(message_id)  # 消息回复结束之后删除流式消息id

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def is_muted(self, group_id: int) -> bool:
        return False

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
        self.listeners.pop(event_type)

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
