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
from Crypto.Cipher import AES

import aiohttp
import lark_oapi.ws.exception
import quart
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
    async def yiri2target(message_chain: platform_message.MessageChain, bot: telegram.Bot):
        pass
    
    @staticmethod
    async def target2yiri(message: telegram.Message, bot: telegram.Bot):
        pass
    

class TelegramEventConverter(adapter.EventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event, bot: telegram.Bot):
        pass
    
    @staticmethod
    async def target2yiri(event: platform_events.Event, bot: telegram.Bot):
        pass
    

@adapter.adapter_class("telegram")
class TelegramMessageSourceAdapter(adapter.MessageSourceAdapter):
    
    bot: telegram.Bot
    application: telegram.ext.Application

    message_converter: TelegramMessageConverter = TelegramMessageConverter()
    event_converter: TelegramEventConverter = TelegramEventConverter()

    config: dict
    ap: app.Application

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, adapter.MessageSourceAdapter], None],
    ] = {}
    
    def __init__(self, config: dict, ap: app.Application):
        self.config = config
        self.ap = ap
        
        async def telegram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.message.from_user.is_bot:
                return
            
            lb_event = await self.event_converter.target2yiri(update, self.bot)
            await self.listeners[type(lb_event)](lb_event, self)
        
        self.application = ApplicationBuilder().token(self.config['token']).build()
        self.bot = self.application.bot
        self.application.add_handler(MessageHandler(filters.TEXT | (filters.COMMAND) | filters.PHOTO, telegram_callback))
        
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
        pass
    
    async def is_muted(self, group_id: int) -> bool:
        return False
    
    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessageSourceAdapter], None],
    ):
        self.listeners[event_type] = callback
    
    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessageSourceAdapter], None],
    ):
        self.listeners.pop(event_type)
    
    async def run_async(self):
        await self.application.initialize()
        await self.application.updater.start_polling()
        await self.application.start()
    
    async def kill(self) -> bool:
        await self.application.stop()
        return True