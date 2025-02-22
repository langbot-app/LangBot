from __future__ import annotations

import telegram
import telegram.ext
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

import typing
import asyncio
import traceback
import time
import re
import base64
import uuid
import json
import datetime
import hashlib
import base64
import aiohttp
from Crypto.Cipher import AES

from flask import jsonify
from lark_oapi.api.im.v1 import *
from lark_oapi.api.verification.v1 import GetVerificationRequest

from .. import adapter
from ...pipeline.longtext.strategies import forward
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities
from ...utils import image


class TelegramMessageConverter(adapter.MessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: telegram.Bot) -> list[dict]:
        components = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                components.append({
                    "type": "text",
                    "text": component.text
                })
            elif isinstance(component, platform_message.Image):

                photo_bytes = None

                if component.base64:
                    photo_bytes = base64.b64decode(component.base64)
                elif component.url:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(component.url) as response:
                            photo_bytes = await response.read()
                elif component.path:
                    with open(component.path, "rb") as f:
                        photo_bytes = f.read()
                
                components.append({
                    "type": "photo",
                    "photo": photo_bytes
                })
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
            message_components.extend(parse_message_text(message.caption))

            file = await message.photo[-1].get_file()

            file_bytes = None
            file_format = ''

            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(file.file_path) as response:
                    file_bytes = await response.read()
                    file_format = 'image/jpeg'

            message_components.append(platform_message.Image(base64=f"data:{file_format};base64,{base64.b64encode(file_bytes).decode('utf-8')}"))
        
        return platform_message.MessageChain(message_components)
    

class TelegramEventConverter(adapter.EventConverter):
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
                    remark=event.effective_chat.id,
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event
            )
        elif event.effective_chat.type == 'group':
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
                    special_title="",
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event
            )
    

class TelegramAdapter(adapter.MessagePlatformAdapter):
    
    bot: telegram.Bot
    application: telegram.ext.Application

    bot_account_id: str

    message_converter: TelegramMessageConverter = TelegramMessageConverter()
    event_converter: TelegramEventConverter = TelegramEventConverter()

    config: dict
    ap: app.Application

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ] = {}
    
    def __init__(self, config: dict, ap: app.Application):
        self.config = config
        self.ap = ap
        
        async def telegram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

            if update.message.from_user.is_bot:
                return

            try:
                lb_event = await self.event_converter.target2yiri(update, self.bot, self.bot_account_id)
                await self.listeners[type(lb_event)](lb_event, self)
            except Exception as e:
                print(traceback.format_exc())
        
        self.application = ApplicationBuilder().token(self.config['token']).build()
        self.bot = self.application.bot
        self.application.add_handler(MessageHandler(filters.TEXT | (filters.COMMAND) | filters.PHOTO , telegram_callback))
        
    async def send_message(
        self, target_type: str, target_id: str, message: platform_message.MessageChain
    ):
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

                args = {
                    "chat_id": message_source.source_platform_object.effective_chat.id,
                    "text": component['text'],
                }

                if quote_origin:
                    args['reply_to_message_id'] = message_source.source_platform_object.message.id

                await self.bot.send_message(**args)
    
    async def is_muted(self, group_id: int) -> bool:
        return False
    
    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        self.listeners[event_type] = callback
    
    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        self.listeners.pop(event_type)
    
    async def run_async(self):
        await self.application.initialize()
        self.bot_account_id = (await self.bot.get_me()).username
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES
        )
        await self.application.start()
    
    async def kill(self) -> bool:
        await self.application.stop()
        return True