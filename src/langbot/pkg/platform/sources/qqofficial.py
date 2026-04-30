from __future__ import annotations
import typing
import re
import asyncio
import traceback

import datetime
import time

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
    # Only treat as base64 if it doesn't look like a URL/path and has valid base64 chars
    if value.startswith(('http://', 'https://', '/', './', '../')):
        return False
    # Check if it looks like base64 (only valid chars, reasonable length)
    return bool(re.fullmatch(r'[A-Za-z0-9+/=\s]{20,}', value))


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
        self._stream_ctx: dict = {}
        self._stream_ctx_ts: dict[str, float] = {}
        self._fallback_text: dict[str, str] = {}
        self._fallback_text_ts: dict[str, float] = {}

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
                await self.logger.warning(f'Event data is not dict, skipping: {event_type} -> {type(event_data)}')
                return
            await self.logger.info(f'Processing message event: {event_type}')
            # 构造与 webhook 模式相同的 payload 结构
            payload = {'t': event_type, 'd': event_data}
            message_data = await self.bot.get_message(payload)
            if message_data:
                event = QQOfficialEvent.from_payload(message_data)
                await self.bot._handle_message(event)

        async def on_error(error: Exception):
            await self.logger.error(f'WebSocket error: {error}')
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

    # --------------- 流式输出 ---------------

    _STREAM_CTX_TTL = 300  # seconds

    async def _cleanup_stale_streams(self):
        """Remove stream contexts that have not been updated for more than _STREAM_CTX_TTL seconds."""
        now = time.time()
        stale_ids = [mid for mid, ts in self._stream_ctx_ts.items() if now - ts > self._STREAM_CTX_TTL]
        for mid in stale_ids:
            self._stream_ctx.pop(mid, None)
            self._stream_ctx_ts.pop(mid, None)
        stale_fb = [mid for mid, ts in self._fallback_text_ts.items() if now - ts > self._STREAM_CTX_TTL]
        for mid in stale_fb:
            self._fallback_text.pop(mid, None)
            self._fallback_text_ts.pop(mid, None)
        if stale_ids or stale_fb:
            await self.logger.debug(f'Cleaned up {len(stale_ids)} stream contexts, {len(stale_fb)} fallback texts')

    async def is_stream_output_supported(self) -> bool:
        return self.config.get('enable-stream-reply', False)

    async def create_message_card(self, message_id: str, event: platform_events.MessageEvent) -> bool:
        source = event.source_platform_object
        # Streaming API only supports C2C private chat
        if source.t != 'C2C_MESSAGE_CREATE':
            return False

        ctx = {
            'user_openid': source.user_openid,
            'msg_id': source.d_id,
            'stream_msg_id': None,
            'msg_seq': 1,
            'index': 0,
            'last_update_ts': 0,
            'accumulated_text': '',
            'sent_length': 0,
            'session_started': False,
        }

        self._stream_ctx[message_id] = ctx
        self._stream_ctx_ts[message_id] = time.time()
        return True

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: dict,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        # Periodically clean up stale stream contexts
        await self._cleanup_stale_streams()
        # 提取纯文本内容（当前 chunk 的文本）
        text_parts = []
        for msg in message:
            if type(msg) is platform_message.Plain:
                text_parts.append(msg.text)
        chunk_text = '\n\n'.join(text_parts)

        message_id = (
            bot_message.get('resp_message_id')
            if isinstance(bot_message, dict)
            else getattr(bot_message, 'resp_message_id', None)
        )
        if not message_id or message_id not in self._stream_ctx:
            # 非流式场景（如群聊不支持流式），累积文本后一次性回复
            if chunk_text:
                self._fallback_text[message_id] = self._fallback_text.get(message_id, '') + chunk_text
                self._fallback_text_ts[message_id] = time.time()
            if is_final:
                full_text = self._fallback_text.pop(message_id, '')
                if full_text:
                    fallback_msg = platform_message.MessageChain([platform_message.Plain(text=full_text)])
                    await self.reply_message(message_source, fallback_msg, quote_origin)
            return

        ctx = self._stream_ctx[message_id]

        # 累积文本
        if chunk_text:
            ctx['accumulated_text'] += chunk_text

        # 未启动会话时，等第一个有内容的 chunk 来建立会话
        if not ctx['session_started']:
            if not ctx['accumulated_text']:
                return
            # 用第一个 chunk 的文本建立会话（不发 "..." 避免污染前缀）
            ctx['session_started'] = True

        # 发送内容 = 全量累积文本
        # QQ API 的 replace 模式不允许修改已下发前缀，所以：
        # - 首次：发送全部文本，建立会话
        # - 后续：只能发送新增部分（append 行为）
        content_to_send = ctx['accumulated_text'][ctx['sent_length'] :]
        if not content_to_send and not is_final:
            return

        input_state = 10 if is_final else 1

        # Rate limiting: skip non-final updates if last update was <0.5s ago
        now = time.time()
        if not is_final and (now - ctx['last_update_ts']) < 0.5:
            return
        ctx['last_update_ts'] = now

        try:
            resp = await self.bot.send_stream_msg(
                user_openid=ctx['user_openid'],
                content=content_to_send,
                event_id=ctx['msg_id'],
                msg_id=ctx['msg_id'],
                msg_seq=ctx['msg_seq'],
                index=ctx['index'],
                stream_msg_id=ctx['stream_msg_id'],
                input_state=input_state,
            )
            if resp and isinstance(resp, dict):
                new_stream_id = resp.get('id')
                if new_stream_id:
                    ctx['stream_msg_id'] = new_stream_id
            ctx['sent_length'] = len(ctx['accumulated_text'])
            ctx['index'] += 1
            await self.logger.debug(
                f'[QQ Official] 流式 chunk 已发送, index={ctx["index"]}, '
                f'sent_len={ctx["sent_length"]}, is_final={is_final}'
            )
        except Exception as e:
            await self.logger.error(f'Failed to send stream message: {e}')

        if is_final:
            self._stream_ctx.pop(message_id, None)

    def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)
