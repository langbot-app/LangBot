from __future__ import annotations

import asyncio
import json
import re
import time
import traceback
import typing
from collections import deque

import aiohttp
import pydantic
import websockets

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

_IMG_B64_RE = re.compile(r'<img_b64>(.*?)</img_b64>', re.DOTALL)


class WeChatFerryMessageDeduplicator:
    """In-memory deduplicator for incoming WCF message IDs."""

    def __init__(self, max_size: int = 4096) -> None:
        self.max_size = max_size
        self._seen_ids: set[str] = set()
        self._order: deque[str] = deque()

    def is_duplicate(self, msg_id: typing.Any) -> bool:
        if not msg_id:
            return False
        key = str(msg_id)
        if key in self._seen_ids:
            return True
        if len(self._order) >= self.max_size:
            oldest = self._order.popleft()
            self._seen_ids.discard(oldest)
        self._seen_ids.add(key)
        self._order.append(key)
        return False


class WeChatFerryMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Converts between LangBot MessageChain and WeChatFerry / Helper V4-V7 payloads."""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> dict:
        """Convert LangBot MessageChain to WCF send request payload."""
        text_parts: list[str] = []
        ats: list[str] = []
        images: list[dict] = []

        for component in message_chain:
            if isinstance(component, platform_message.AtAll):
                ats.append('notify@all')
            elif isinstance(component, platform_message.At):
                if component.target:
                    ats.append(str(component.target))
            elif isinstance(component, platform_message.Plain):
                if component.text:
                    text_parts.append(str(component.text))
            elif isinstance(component, platform_message.Image):
                img_info = {}
                if component.url:
                    img_info['url'] = component.url
                elif component.base64:
                    img_info['base64'] = component.base64
                elif component.path:
                    img_info['path'] = component.path
                if img_info:
                    images.append(img_info)

        return {
            'text': ''.join(text_parts),
            'ats': ats,
            'images': images,
        }

    @staticmethod
    async def target2yiri(
        data: dict,
        bot_account_id: str,
    ) -> platform_message.MessageChain:
        """Convert WCF / Helper V4-V7 incoming message dictionary to LangBot MessageChain."""
        components: list[platform_message.MessageComponent] = []

        content = data.get('content') or ''
        is_at = bool(data.get('is_at', False))
        msg_type = data.get('type', 1)

        # 检查是否被 @
        if is_at and bot_account_id:
            components.append(platform_message.At(target=bot_account_id))

        if '@所有人' in content:
            components.append(platform_message.AtAll())

        if msg_type == 1:  # 文本消息
            if content:
                components.append(platform_message.Plain(text=content))
        elif msg_type == 3:  # 图片消息（优先提取网关内联 <img_b64>，并拦截跨机 Windows 盘符路径）
            b64_match = _IMG_B64_RE.search(content)
            img_b64 = (b64_match.group(1).strip() if b64_match else '') or str(
                data.get('img_b64') or data.get('base64') or ''
            ).strip()
            img_path = str(data.get('extra') or data.get('image_path') or '').strip()
            if img_b64:
                if not img_b64.startswith('data:'):
                    img_b64 = f'data:image/jpeg;base64,{img_b64}'
                data['content'] = '[图片]'
                components.append(platform_message.Image(base64=img_b64))
            elif img_path and ':' not in img_path:
                components.append(platform_message.Image(path=img_path))
            else:
                components.append(platform_message.Plain(text='[图片]'))
        else:
            if content:
                components.append(platform_message.Plain(text=content))
            else:
                components.append(platform_message.Unknown(text=f'[未知类型: {msg_type}]'))

        return platform_message.MessageChain(components)


class WeChatFerryEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Converts incoming WCF / Helper V4-V7 message dict to LangBot GroupMessage or FriendMessage."""

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        self.config = config
        self.logger = logger
        self.message_converter = WeChatFerryMessageConverter()

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict:
        return {}

    async def target2yiri(
        self,
        event: dict,
        bot_account_id: str,
    ) -> typing.Optional[platform_events.MessageEvent]:
        sender = str(event.get('sender') or '')
        roomid = str(event.get('roomid') or '')
        bot_wxid = str(self.config.get('bot_wxid') or '')

        # 过滤自身消息、微信官方服务消息
        if not sender:
            return None
        if bot_wxid and sender == bot_wxid:
            return None
        if sender.startswith('gh_') or sender in {'weixin', 'newsapp', 'fmessage', 'medianote', 'qmessage'}:
            return None

        message_chain = await self.message_converter.target2yiri(event, bot_account_id)
        if not message_chain:
            return None

        event_time = event.get('ts') or int(time.time())
        sender_name = str(event.get('sender_name') or sender)
        room_name = str(event.get('room_name') or roomid)

        is_group = bool(event.get('is_group', False)) or ('@chatroom' in roomid)

        if is_group:
            # 群聊消息：sender 为群成员真实 wxid，member_name 优先透传网关解析出的真实群昵称
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender,
                    member_name=sender_name,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=roomid,
                        name=room_name,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=message_chain,
                time=event_time,
                source_platform_object=event,
            )
        else:
            # 私聊消息：sender 为用户真实 wxid，nickname 优先透传真实显示名
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=sender,
                    nickname=sender_name,
                    remark='',
                ),
                message_chain=message_chain,
                time=event_time,
                source_platform_object=event,
            )


class WeChatFerryAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """WeChatFerry / WeChat 4.x Helper Native Bridge PC 微信平台适配器"""

    model_config = pydantic.ConfigDict(extra='allow', arbitrary_types_allowed=True)

    name: str = 'wechatferry'
    bot_account_id: str = ''
    config: dict = pydantic.Field(default_factory=dict)
    logger: typing.Any = None
    message_converter: typing.Any = None
    event_converter: typing.Any = None
    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = pydantic.Field(default_factory=dict)

    _deduplicator: WeChatFerryMessageDeduplicator = pydantic.PrivateAttr(default_factory=WeChatFerryMessageDeduplicator)
    _running: bool = pydantic.PrivateAttr(default=False)
    _ws_task: typing.Optional[asyncio.Task] = pydantic.PrivateAttr(default=None)
    _inbound_tasks: set[asyncio.Task] = pydantic.PrivateAttr(default_factory=set)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        message_converter = WeChatFerryMessageConverter()
        event_converter = WeChatFerryEventConverter(config, logger)
        bot_wxid = config.get('bot_wxid', '')

        super().__init__(
            config=config,
            logger=logger,
            message_converter=message_converter,
            event_converter=event_converter,
            listeners={},
            bot_account_id=bot_wxid,
            name='wechatferry',
            **kwargs,
        )
        self.message_converter = message_converter
        self.event_converter = event_converter
        self.listeners = {}

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        self.listeners.pop(event_type, None)

    async def run_async(self):
        """启动适配器，连接 WCF WebSocket 服务并持续接收消息"""
        self._running = True
        ws_url = self.config.get('ws_url', 'ws://127.0.0.1:18080/ws')
        api_url = self.config.get('api_url', 'http://127.0.0.1:18080')

        await self.logger.info(f'WeChatFerry 适配器正在启动，API 地址: {api_url}, WS 地址: {ws_url}...')

        # 尝试查询一次 WCF 账号状态，自动同步当前登录账号 self_wxid
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{api_url}/api/status', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        status_data = await resp.json()
                        if status_data.get('is_login'):
                            self.bot_account_id = status_data.get('self_wxid') or self.bot_account_id
                            self.config['bot_wxid'] = self.bot_account_id
                            user_info = status_data.get('user_info', {})
                            await self.logger.info(
                                f'WeChatFerry 账号已在线: {user_info.get("name", "WeChat")} ({self.bot_account_id})'
                            )
        except Exception as e:
            await self.logger.warning(f'检查 WCF 账号状态失败 (非致命): {e}')

        self._ws_task = asyncio.create_task(self._ws_loop(ws_url))

        try:
            await self._ws_task
        except asyncio.CancelledError:
            pass

    async def _ws_loop(self, ws_url: str):
        """WebSocket 消息监听循环，支持 64MiB 大帧（适配图片/语音/35MiB 文档内联）与自动断线重连"""
        retry_delay = 2.0
        max_retry_delay = 30.0
        ws_max_size_mb = max(16, int(self.config.get('ws_max_size_mb', 64) or 64))
        ws_max_size = ws_max_size_mb * 1024 * 1024

        while self._running:
            try:
                await self.logger.info(f'正在连接 WeChatFerry WebSocket: {ws_url} (max_size={ws_max_size_mb}MiB) ...')
                async with websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    max_size=ws_max_size,
                ) as ws:
                    await self.logger.info('WeChatFerry WebSocket 连接成功，开始接收微信消息！')
                    retry_delay = 2.0  # 连接成功后重置重试间隔

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            if isinstance(message, bytes):
                                message = message.decode('utf-8', errors='ignore')
                            data = json.loads(message)
                            task = asyncio.create_task(self._handle_inbound_data(data))
                            self._inbound_tasks.add(task)
                            task.add_done_callback(self._inbound_tasks.discard)
                        except json.JSONDecodeError:
                            await self.logger.warning(f'收到非 JSON 格式消息: {message[:100]}')
                        except Exception as ex:
                            await self.logger.error(f'处理 WCF 消息异常: {ex}\n{traceback.format_exc()}')

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                await self.logger.error(f'WeChatFerry WebSocket 连接断开 ({e})，将在 {retry_delay:.1f} 秒后重试...')
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, max_retry_delay)

    async def _handle_inbound_data(self, data: dict):
        """处理由 WebSocket 推送过来的单条微信消息"""
        try:
            msg_id = data.get('id') or data.get('msg_id')
            if msg_id and self._deduplicator.is_duplicate(msg_id):
                return

            event = await self.event_converter.target2yiri(data, self.bot_account_id)
            if event is not None and event.__class__ in self.listeners:
                await self.listeners[event.__class__](event, self)
        except Exception as ex:
            await self.logger.error(f'分发 WCF 入站事件异常: {ex}\n{traceback.format_exc()}')

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ):
        """主动发送消息至群聊或私聊"""
        api_url = self.config.get('api_url', 'http://127.0.0.1:18080')
        payload = await self.message_converter.yiri2target(message)

        text = payload.get('text', '')
        ats = payload.get('ats', [])
        images = payload.get('images', [])

        aters_str = ','.join(ats) if ats else ''

        async with aiohttp.ClientSession() as session:
            # 1. 发送文本消息
            if text:
                send_data = {
                    'receiver': target_id,
                    'msg': text,
                    'aters': aters_str,
                }
                try:
                    async with session.post(
                        f'{api_url}/api/send',
                        json=send_data,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        res_json = await resp.json()
                        if res_json.get('status') != 0:
                            await self.logger.error(f'WCF 发送文本失败: {res_json}')
                except Exception as e:
                    await self.logger.error(f'请求 WCF 发送文本异常: {e}')

            # 2. 发送图片消息
            for img in images:
                img_data = {
                    'receiver': target_id,
                    'path': img.get('path', ''),
                    'url': img.get('url', ''),
                    'base64': img.get('base64', ''),
                }
                try:
                    async with session.post(
                        f'{api_url}/api/send_image',
                        json=img_data,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        res_json = await resp.json()
                        if res_json.get('status') != 0:
                            await self.logger.error(f'WCF 发送图片失败: {res_json}')
                except Exception as e:
                    await self.logger.error(f'请求 WCF 发送图片异常: {e}')

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """回复消息（路由回群聊 roomid 或私聊 wxid）"""
        if isinstance(message_source, platform_events.GroupMessage):
            target_id = message_source.sender.group.id
            await self.send_message('group', target_id, message)
        elif isinstance(message_source, platform_events.FriendMessage):
            target_id = message_source.sender.id
            await self.send_message('person', target_id, message)
        else:
            obj = getattr(message_source, 'source_platform_object', {})
            target_id = obj.get('roomid') or obj.get('sender')
            if target_id:
                await self.send_message('unknown', target_id, message)

    async def is_muted(self, group_id: int) -> bool:
        return False

    async def kill(self) -> bool:
        """优雅关闭适配器"""
        self._running = False
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
        for task in list(self._inbound_tasks):
            if not task.done():
                task.cancel()
        return True
