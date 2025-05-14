from __future__ import annotations
import typing
import asyncio
import traceback

import datetime

from pkg.platform.adapter import MessagePlatformAdapter
from pkg.platform.types import events as platform_events, message as platform_message
from .. import adapter
from ...core import app
from ..types import entities as platform_entities
from ...command.errors import ParamNotEnoughError
from libs.qq_official_api.api import QQOfficialClient
from libs.qq_official_api.qqofficialevent import QQOfficialEvent
from ...utils import image


class QQOfficialMessageConverter(adapter.MessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        content_list = []
        # 只实现了发文字
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                content_list.append(
                    {
                        'type': 'text',
                        'content': msg.text,
                    }
                )

        return content_list

    @staticmethod
    async def target2yiri(message: str, message_id: str, pic_url: str, content_type):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))
        if pic_url is not None:
            base64_url = await image.get_qq_official_image_base64(pic_url=pic_url, content_type=content_type)
            yiri_msg_list.append(platform_message.Image(base64=base64_url))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)
        return chain


class QQOfficialEventConverter(adapter.EventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> QQOfficialEvent:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: QQOfficialEvent):
        """
        QQ官方消息转换为LB对象
        """
        yiri_chain = await QQOfficialMessageConverter.target2yiri(
            message=event.content,
            message_id=event.d_id,
            pic_url=event.attachments,
            content_type=event.content_type,
        )

        if event.t == 'C2C_MESSAGE_CREATE':
            friend = platform_entities.Friend(
                id=event.user_openid,
                nickname=event.t,
                remark='',
            )
            return platform_events.FriendMessage(
                sender=friend,
                message_chain=yiri_chain,
                time=int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp()),
                source_platform_object=event,
            )

        if event.t == 'DIRECT_MESSAGE_CREATE':
            friend = platform_entities.Friend(
                id=event.guild_id,
                nickname=event.t,
                remark='',
            )
            return platform_events.FriendMessage(sender=friend, message_chain=yiri_chain, source_platform_object=event)
        if event.t == 'GROUP_AT_MESSAGE_CREATE':
            yiri_chain.insert(0, platform_message.At(target='justbot'))

            sender = platform_entities.GroupMember(
                id=event.group_openid,
                member_name=event.t,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=event.group_openid,
                    name='MEMBER',
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
                join_timestamp=0,
                last_speak_timestamp=0,
                mute_time_remaining=0,
            )
            time = int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp())
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=yiri_chain,
                time=time,
                source_platform_object=event,
            )
        if event.t == 'AT_MESSAGE_CREATE':
            yiri_chain.insert(0, platform_message.At(target='justbot'))
            sender = platform_entities.GroupMember(
                id=event.channel_id,
                member_name=event.t,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=event.channel_id,
                    name='MEMBER',
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
                join_timestamp=0,
                last_speak_timestamp=0,
                mute_time_remaining=0,
            )
            time = int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp())
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=yiri_chain,
                time=time,
                source_platform_object=event,
            )


class QQOfficialAdapter(adapter.MessagePlatformAdapter):
    bot: QQOfficialClient
    ap: app.Application
    config: dict
    bot_account_id: str
    message_converter: QQOfficialMessageConverter = QQOfficialMessageConverter()
    event_converter: QQOfficialEventConverter = QQOfficialEventConverter()

    def __init__(self, config: dict, ap: app.Application):
        self.config = config
        self.ap = ap

        required_keys = [
            'appid',
            'secret',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ParamNotEnoughError('QQ官方机器人缺少相关配置项，请查看文档或联系管理员')

        self.bot = QQOfficialClient(
            app_id=config['appid'],
            secret=config['secret'],
            token=config['token'],
        )

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        qq_official_event = await QQOfficialEventConverter.yiri2target(
            message_source,
        )

        content_list = await QQOfficialMessageConverter.yiri2target(message)

        # 私聊消息
        if qq_official_event.t == 'C2C_MESSAGE_CREATE':
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_private_text_msg(
                        qq_official_event.user_openid,
                        content['content'],
                        qq_official_event.d_id,
                    )

        # 群聊消息
        if qq_official_event.t == 'GROUP_AT_MESSAGE_CREATE':
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_group_text_msg(
                        qq_official_event.group_openid,
                        content['content'],
                        qq_official_event.d_id,
                    )

        # 频道群聊
        if qq_official_event.t == 'AT_MESSAGE_CREATE':
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_channle_group_text_msg(
                        qq_official_event.channel_id,
                        content['content'],
                        qq_official_event.d_id,
                    )

        # 频道私聊
        if qq_official_event.t == 'DIRECT_MESSAGE_CREATE':
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_channle_private_text_msg(
                        qq_official_event.guild_id,
                        content['content'],
                        qq_official_event.d_id,
                    )

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        async def on_message(event: QQOfficialEvent):
            self.bot_account_id = 'justbot'
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                traceback.print_exc()

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('DIRECT_MESSAGE_CREATE')(on_message)
            self.bot.on_message('C2C_MESSAGE_CREATE')(on_message)
        elif event_type == platform_events.GroupMessage:
            self.bot.on_message('GROUP_AT_MESSAGE_CREATE')(on_message)
            self.bot.on_message('AT_MESSAGE_CREATE')(on_message)

    async def run_async(self):
        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.bot.run_task(
            host='0.0.0.0',
            port=self.config['port'],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        return False

    def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[[platform_events.Event, MessagePlatformAdapter], None],
    ):
        return super().unregister_listener(event_type, callback)
