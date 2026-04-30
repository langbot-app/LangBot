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


def _is_base64_data(value: str) -> bool:
    """Check if a string contains base64-encoded data rather than a URL."""
    if not value:
        return False
    # data: URI scheme (e.g. data:image/png;base64,xxx)
    if value.startswith('data:'):
        return True
    # If it doesn't look like a URL, treat as raw base64
    if not value.startswith(('http://', 'https://')):
        return True
    return False


class QQOfficialMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        """将 LangBot 消息链转换为 QQ Official 消息格式列表。"""
        content_list = []
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                content_list.append(
                    {
                        'type': 'text',
                        'content': msg.text,
                    }
                )
            elif type(msg) is platform_message.Image:
                url = msg.url if hasattr(msg, 'url') and msg.url else None
                b64 = msg.base64 if hasattr(msg, 'base64') and msg.base64 else None
                # Some plugins (e.g. MimoTTS) store base64 data in the url field
                if url and not b64 and _is_base64_data(url):
                    b64 = url
                    url = None
                content_list.append(
                    {
                        'type': 'image',
                        'url': url,
                        'base64': b64,
                    }
                )
            elif type(msg) is platform_message.Voice:
                url = msg.url if hasattr(msg, 'url') and msg.url else None
                b64 = msg.base64 if hasattr(msg, 'base64') and msg.base64 else None
                # Some plugins (e.g. MimoTTS) store base64 data in the url field
                if url and not b64 and _is_base64_data(url):
                    b64 = url
                    url = None
                content_list.append(
                    {
                        'type': 'voice',
                        'url': url,
                        'base64': b64,
                    }
                )
            elif type(msg) is platform_message.File:
                url = msg.url if hasattr(msg, 'url') and msg.url else None
                b64 = msg.base64 if hasattr(msg, 'base64') and msg.base64 else None
                # Some plugins store base64 data in the url field
                if url and not b64 and _is_base64_data(url):
                    b64 = url
                    url = None
                content_list.append(
                    {
                        'type': 'file',
                        'url': url,
                        'base64': b64,
                        'name': msg.name if hasattr(msg, 'name') else 'file',
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


class QQOfficialEventConverter(abstract_platform_adapter.AbstractEventConverter):
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
    enable_webhook: bool = False
    message_converter: QQOfficialMessageConverter = QQOfficialMessageConverter()
    event_converter: QQOfficialEventConverter = QQOfficialEventConverter()

    def __init__(self, config: dict, logger: EventLogger):
        enable_webhook = config.get('enable-webhook', False)

        bot = QQOfficialClient(
            app_id=config['appid'],
            secret=config['secret'],
            token=config['token'],
            logger=logger,
            unified_mode=enable_webhook,
        )

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=config['appid'],
        )

        self.enable_webhook = enable_webhook
        self._ws_task: asyncio.Task = None

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

        # 确定 target_type 和 target_id
        target_type = None
        target_id = None

        if qq_official_event.t == 'C2C_MESSAGE_CREATE':
            target_type = 'c2c'
            target_id = qq_official_event.user_openid
        elif qq_official_event.t == 'GROUP_AT_MESSAGE_CREATE':
            target_type = 'group'
            target_id = qq_official_event.group_openid
        elif qq_official_event.t == 'AT_MESSAGE_CREATE':
            # 频道群聊使用频道 API，暂不支持富媒体
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_channle_group_text_msg(
                        qq_official_event.channel_id,
                        content['content'],
                        qq_official_event.d_id,
                    )
            return
        elif qq_official_event.t == 'DIRECT_MESSAGE_CREATE':
            # 频道私聊使用频道 API，暂不支持富媒体
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_channle_private_text_msg(
                        qq_official_event.guild_id,
                        content['content'],
                        qq_official_event.d_id,
                    )
            return

        # C2C 和群聊：支持文字 + 富媒体
        for content in content_list:
            content_type = content.get('type', 'text')

            if content_type == 'text':
                if target_type == 'c2c':
                    await self.bot.send_private_text_msg(
                        target_id,
                        content['content'],
                        qq_official_event.d_id,
                    )
                elif target_type == 'group':
                    await self.bot.send_group_text_msg(
                        target_id,
                        content['content'],
                        qq_official_event.d_id,
                    )

            elif content_type == 'image':
                file_url = content.get('url')
                file_data = content.get('base64')
                if file_url or file_data:
                    await self.bot.send_image_msg(
                        target_type,
                        target_id,
                        file_url=file_url,
                        file_data=file_data,
                        msg_id=qq_official_event.d_id,
                    )

            elif content_type == 'voice':
                file_url = content.get('url')
                file_data = content.get('base64')
                if file_url or file_data:
                    await self.bot.send_voice_msg(
                        target_type,
                        target_id,
                        file_url=file_url,
                        file_data=file_data,
                        msg_id=qq_official_event.d_id,
                    )

            elif content_type == 'file':
                file_url = content.get('url')
                file_data = content.get('base64')
                file_name = content.get('name', 'file')
                if file_url or file_data:
                    await self.bot.send_file_msg(
                        target_type,
                        target_id,
                        file_url=file_url,
                        file_data=file_data,
                        file_name=file_name,
                        msg_id=qq_official_event.d_id,
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
        if not self.enable_webhook:
            await self._run_websocket()
        else:
            # 统一 webhook 模式下，不启动独立的 Quart 应用
            async def keep_alive():
                while True:
                    await asyncio.sleep(1)

            await keep_alive()

    async def _run_websocket(self):
        """以 WebSocket 模式运行网关连接"""
        await self.logger.info('QQ Official adapter starting in WebSocket mode')

        async def on_ready():
            await self.logger.info('QQ Official WebSocket connected and ready')

        async def on_event(event_type: str, event_data: dict):
            # 只处理消息事件，忽略 READY/RESUMED 等系统事件
            message_event_types = {
                'C2C_MESSAGE_CREATE',
                'DIRECT_MESSAGE_CREATE',
                'GROUP_AT_MESSAGE_CREATE',
                'AT_MESSAGE_CREATE',
            }
            if event_type not in message_event_types:
                return
            if not isinstance(event_data, dict):
                print(f'[QQ Official WS] 事件 data 不是 dict，跳过: {event_type} -> {type(event_data)}')
                return
            print(f'[QQ Official WS] 处理消息事件: {event_type}')
            # 构造与 webhook 模式相同的 payload 结构
            payload = {'t': event_type, 'd': event_data}
            message_data = await self.bot.get_message(payload)
            if message_data:
                event = QQOfficialEvent.from_payload(message_data)
                await self.bot._handle_message(event)

        async def on_error(error: Exception):
            print(f'[QQ Official WS] ❌ 错误: {error}')
            await self.logger.error(f'QQ Official WebSocket error: {error}')

        self._ws_task = asyncio.create_task(self.bot.connect_gateway_loop(on_event, on_ready, on_error))
        try:
            await self._ws_task
        except asyncio.CancelledError:
            pass

    async def kill(self) -> bool:
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        return True

    def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)
