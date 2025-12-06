from __future__ import annotations
import typing
import asyncio
import traceback

import datetime

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from langbot.libs.qq_official_api.api import QQOfficialClient
from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from ...utils import image
from ..logger import EventLogger


class QQOfficialMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    def __init__(self, bot: QQOfficialClient = None):
        self.bot = bot

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

    async def target2yiri(self, message: str, message_id: str, pic_url: str, content_type, message_reference: dict = None, event_type: str = None, channel_id: str = None, group_openid: str = None, user_openid: str = None):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))
        
        # Handle quoted message if message_reference exists
        if message_reference and message_reference.get('message_id') and self.bot:
            referenced_msg_id = message_reference.get('message_id')
            try:
                # Fetch the referenced message
                referenced_msg = await self.bot.get_message_by_id(
                    referenced_msg_id,
                    channel_id=channel_id,
                    group_openid=group_openid,
                    user_openid=user_openid
                )
                
                if referenced_msg:
                    # Create message chain for the quoted content
                    quoted_content = referenced_msg.get('content', '')
                    quoted_chain = platform_message.MessageChain()
                    
                    if quoted_content:
                        quoted_chain.append(platform_message.Plain(text=quoted_content))
                    
                    # Add images if present in quoted message
                    quoted_attachments = referenced_msg.get('attachments', [])
                    for attachment in quoted_attachments:
                        if attachment.get('content_type', '').startswith('image/'):
                            img_url = attachment.get('url', '')
                            if img_url:
                                try:
                                    img_base64 = await image.get_qq_official_image_base64(
                                        pic_url=img_url if img_url.startswith('https://') else 'https://' + img_url,
                                        content_type=attachment.get('content_type', '')
                                    )
                                    quoted_chain.append(platform_message.Image(base64=img_base64))
                                except Exception:
                                    # If image fetch fails, just skip it
                                    pass
                    
                    # Get sender info from referenced message
                    quoted_sender_id = referenced_msg.get('author', {}).get('id', '') or \
                                     referenced_msg.get('author', {}).get('user_openid', '') or \
                                     referenced_msg.get('author', {}).get('member_openid', '')
                    
                    # Add Quote component
                    yiri_msg_list.append(
                        platform_message.Quote(
                            id=referenced_msg_id,
                            sender_id=quoted_sender_id,
                            origin=quoted_chain,
                        )
                    )
            except Exception as e:
                # If fetching quoted message fails, log and continue
                await self.bot.logger.warning(f'Failed to fetch quoted message {referenced_msg_id}: {e}')
        
        if pic_url is not None:
            base64_url = await image.get_qq_official_image_base64(pic_url=pic_url, content_type=content_type)
            yiri_msg_list.append(platform_message.Image(base64=base64_url))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)
        return chain


class QQOfficialEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self, message_converter: QQOfficialMessageConverter):
        self.message_converter = message_converter

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> QQOfficialEvent:
        return event.source_platform_object

    async def target2yiri(self, event: QQOfficialEvent):
        """
        QQ官方消息转换为LB对象
        """
        # Get message reference if present
        message_reference = event.message_reference
        
        # Determine context based on event type
        channel_id = event.channel_id if event.t in ['AT_MESSAGE_CREATE', 'DIRECT_MESSAGE_CREATE'] else None
        group_openid = event.group_openid if event.t == 'GROUP_AT_MESSAGE_CREATE' else None
        user_openid = event.user_openid if event.t == 'C2C_MESSAGE_CREATE' else None
        
        yiri_chain = await self.message_converter.target2yiri(
            message=event.content,
            message_id=event.d_id,
            pic_url=event.attachments,
            content_type=event.content_type,
            message_reference=message_reference,
            event_type=event.t,
            channel_id=channel_id,
            group_openid=group_openid,
            user_openid=user_openid,
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
            )
            time = int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp())
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=yiri_chain,
                time=time,
                source_platform_object=event,
            )


class QQOfficialAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: QQOfficialClient
    config: dict
    bot_account_id: str
    bot_uuid: str = None
    message_converter: QQOfficialMessageConverter
    event_converter: QQOfficialEventConverter

    def __init__(self, config: dict, logger: EventLogger):
        bot = QQOfficialClient(
            app_id=config['appid'], secret=config['secret'], token=config['token'], logger=logger, unified_mode=True
        )

        # Initialize converters with bot reference
        message_converter = QQOfficialMessageConverter(bot=bot)
        event_converter = QQOfficialEventConverter(message_converter=message_converter)

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=config['appid'],
        )
        
        self.message_converter = message_converter
        self.event_converter = event_converter

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
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: QQOfficialEvent):
            self.bot_account_id = 'justbot'
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                await self.logger.error(f'Error in qqofficial callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('DIRECT_MESSAGE_CREATE')(on_message)
            self.bot.on_message('C2C_MESSAGE_CREATE')(on_message)
        elif event_type == platform_events.GroupMessage:
            self.bot.on_message('GROUP_AT_MESSAGE_CREATE')(on_message)
            self.bot.on_message('AT_MESSAGE_CREATE')(on_message)

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        """处理统一 webhook 请求。

        Args:
            bot_uuid: Bot 的 UUID
            path: 子路径（如果有的话）
            request: Quart Request 对象

        Returns:
            响应数据
        """
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        # 统一 webhook 模式下，不启动独立的 Quart 应用
        # 保持运行但不启动独立端口

        async def keep_alive():
            while True:
                await asyncio.sleep(1)

        await keep_alive()

    async def kill(self) -> bool:
        return False

    def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)
