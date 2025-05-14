from __future__ import annotations
import typing
import asyncio
import traceback

import datetime
from pkg.platform.adapter import MessagePlatformAdapter
from pkg.platform.types import events as platform_events, message as platform_message
from libs.official_account_api.oaevent import OAEvent
from libs.official_account_api.api import OAClient
from libs.official_account_api.api import OAClientForLongerResponse
from .. import adapter
from ...core import app
from ..types import entities as platform_entities
from ...command.errors import ParamNotEnoughError


class OAMessageConverter(adapter.MessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                return msg.text

    @staticmethod
    async def target2yiri(message: str, message_id=-1):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class OAEventConverter(adapter.EventConverter):
    @staticmethod
    async def target2yiri(event: OAEvent):
        if event.type == 'text':
            yiri_chain = await OAMessageConverter.target2yiri(event.message, event.message_id)

            friend = platform_entities.Friend(
                id=event.user_id,
                nickname=str(event.user_id),
                remark='',
            )

            return platform_events.FriendMessage(
                sender=friend,
                message_chain=yiri_chain,
                time=event.timestamp,
                source_platform_object=event,
            )
        else:
            return None


class OfficialAccountAdapter(adapter.MessagePlatformAdapter):
    bot: OAClient | OAClientForLongerResponse
    ap: app.Application
    bot_account_id: str
    message_converter: OAMessageConverter = OAMessageConverter()
    event_converter: OAEventConverter = OAEventConverter()
    config: dict

    def __init__(self, config: dict, ap: app.Application):
        self.config = config

        self.ap = ap

        required_keys = [
            'token',
            'EncodingAESKey',
            'AppSecret',
            'AppID',
            'Mode',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ParamNotEnoughError('微信公众号缺少相关配置项，请查看文档或联系管理员')

        if self.config['Mode'] == 'drop':
            self.bot = OAClient(
                token=config['token'],
                EncodingAESKey=config['EncodingAESKey'],
                Appsecret=config['AppSecret'],
                AppID=config['AppID'],
            )
        elif self.config['Mode'] == 'passive':
            self.bot = OAClientForLongerResponse(
                token=config['token'],
                EncodingAESKey=config['EncodingAESKey'],
                Appsecret=config['AppSecret'],
                AppID=config['AppID'],
                LoadingMessage=config['LoadingMessage'],
            )
        else:
            raise KeyError('请设置微信公众号通信模式')

    async def reply_message(
        self,
        message_source: platform_events.FriendMessage,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        content = await OAMessageConverter.yiri2target(message)
        if isinstance(self.bot, OAClient):
            await self.bot.set_message(message_source.message_chain.message_id, content)
        elif isinstance(self.bot, OAClientForLongerResponse):
            from_user = message_source.sender.id
            await self.bot.set_message(from_user, message_source.message_chain.message_id, content)

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    def register_listener(
        self,
        event_type: type,
        callback: typing.Callable[[platform_events.Event, MessagePlatformAdapter], None],
    ):
        async def on_message(event: OAEvent):
            self.bot_account_id = event.receiver_id
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                traceback.print_exc()

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('text')(on_message)
        elif event_type == platform_events.GroupMessage:
            pass

    async def run_async(self):
        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.bot.run_task(
            host=self.config['host'],
            port=self.config['port'],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[[platform_events.Event, MessagePlatformAdapter], None],
    ):
        return super().unregister_listener(event_type, callback)
