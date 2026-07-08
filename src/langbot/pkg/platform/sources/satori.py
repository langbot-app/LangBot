from __future__ import annotations

import typing
import time
import datetime
import json
import asyncio
import traceback
import re
import base64

import aiohttp
import pydantic
import websockets

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class SatoriMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Convert between LangBot MessageChain and Satori message format"""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, adapter: 'SatoriAdapter') -> str:
        """Convert LangBot MessageChain to Satori message format"""
        content_parts = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                text = component.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                content_parts.append(text)
            elif isinstance(component, platform_message.Image):
                # Prefer URL over base64 to avoid buffer overflow issues with large images
                if component.url:
                    content_parts.append(f'<img src="{component.url}"/>')
                elif hasattr(component, 'base64') and component.base64:
                    # Process base64 data
                    base64_data = component.base64
                    # Remove whitespace that might corrupt the data
                    base64_data = base64_data.replace('\n', '').replace('\r', '').replace(' ', '')

                    # Check size - if too large, try to upload
                    MAX_INLINE_SIZE = 32 * 1024  # 32KB limit for inline base64

                    # Extract raw base64 and mime type
                    raw_b64 = base64_data
                    mime_type = 'image/png'
                    if base64_data.startswith('data:'):
                        try:
                            header, raw_b64 = base64_data.split(',', 1)
                            if ';' in header:
                                mime_type = header.split(':')[1].split(';')[0]
                        except (ValueError, IndexError):
                            pass

                    if len(raw_b64) > MAX_INLINE_SIZE:
                        # Try to upload large image
                        try:
                            # Fix base64 padding if needed
                            padding = 4 - len(raw_b64) % 4
                            if padding != 4:
                                raw_b64 += '=' * padding
                            image_bytes = base64.b64decode(raw_b64)
                            uploaded_url = await adapter.upload_image(image_bytes, mime_type)
                            if uploaded_url:
                                await adapter.logger.info(f'Satori 图片上传成功: {len(image_bytes)} 字节')
                                content_parts.append(f'<img src="{uploaded_url}"/>')
                            else:
                                # Upload failed, use inline (may fail)
                                await adapter.logger.warning('Satori 图片上传失败，使用内联模式')
                                content_parts.append(f'<img src="data:{mime_type};base64,{raw_b64}"/>')
                        except Exception as e:
                            await adapter.logger.error(f'Satori 图片处理失败: {e}')
                            content_parts.append(f'<img src="data:{mime_type};base64,{raw_b64}"/>')
                    else:
                        # Small image, use inline
                        content_parts.append(f'<img src="data:{mime_type};base64,{raw_b64}"/>')
            elif isinstance(component, platform_message.At):
                if component.target:
                    content_parts.append(f'<at id="{component.target}"/>')
            elif isinstance(component, platform_message.AtAll):
                content_parts.append('<at type="all"/>')
            elif isinstance(component, platform_message.Reply):
                content_parts.append(f'<reply id="{component.id}"/>')
            elif isinstance(component, platform_message.Quote):
                content_parts.append(f'<quote id="{component.message_id}"/>')
            elif isinstance(component, platform_message.Face):
                # Satori中的表情可以使用emoticon元素
                face_id = getattr(component, 'face_id', 'unknown')
                content_parts.append(f'<emoticon id="{face_id}"/>')
            elif isinstance(component, platform_message.Voice):
                if hasattr(component, 'url') and component.url:
                    content_parts.append(f'<audio src="{component.url}"/>')
            elif isinstance(component, platform_message.File):
                if hasattr(component, 'url') and component.url:
                    content_parts.append(f'<file url="{component.url}" name="{getattr(component, "name", "")}"/>')

        return ''.join(content_parts)

    @staticmethod
    async def target2yiri(
        message_data: dict, adapter: 'SatoriAdapter', bot_account_id: str = ''
    ) -> platform_message.MessageChain:
        """Convert Satori message to LangBot MessageChain

        Parses Satori's XML-like message format and converts to LangBot MessageChain.
        Handles text, images, mentions, replies, quotes, emoticons, audio, and files.
        """
        content = message_data.get('content', '')

        components = []

        if content:
            # HTML实体解码 - 注意顺序：先解码 &amp; 再解码其他实体
            # 这样可以正确处理 &amp;lt; -> &lt; -> <
            content = content.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

            # 定义各种消息组件的正则模式 - 支持更灵活的属性顺序
            # 使用 (?:...) 非捕获组来支持可选属性
            patterns = [
                # 图片 - 支持 src 在任意位置
                (r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*/?\s*>', 'image'),
                # @提及用户 - id 属性
                (r'<at\s+[^>]*id=["\']([^"\']+)["\'][^>]*/?\s*>', 'mention'),
                # @全体 - type="all"
                (r'<at\s+[^>]*type=["\']all["\'][^>]*/?\s*>', 'mention_all'),
                # 回复
                (r'<reply\s+[^>]*id=["\']([^"\']+)["\'][^>]*/?\s*>', 'reply'),
                # 引用
                (r'<quote\s+[^>]*id=["\']([^"\']+)["\'][^>]*/?\s*>', 'quote'),
                # 表情
                (r'<emoticon\s+[^>]*id=["\']([^"\']+)["\'][^>]*/?\s*>', 'emoticon'),
                (r'<face\s+[^>]*id=["\']([^"\']+)["\'][^>]*/?\s*>', 'face'),
                # 音频
                (r'<audio\s+[^>]*src=["\']([^"\']+)["\'][^>]*/?\s*>', 'audio'),
                (r'<record\s+[^>]*(?:src|url)=["\']([^"\']+)["\'][^>]*/?\s*>', 'audio'),
                # 视频
                (r'<video\s+[^>]*src=["\']([^"\']+)["\'][^>]*/?\s*>', 'video'),
                # 文件 - 支持 url 或 src 属性
                (r'<file\s+[^>]*(?:url|src)=["\']([^"\']+)["\'][^>]*/?\s*>', 'file'),
            ]

            # 构建联合正则表达式
            combined_pattern = '|'.join([f'({p[0]})' for p in patterns])

            # 分割消息内容，按顺序处理各种组件
            pos = 0
            for match in re.finditer(combined_pattern, content, re.IGNORECASE):
                # 添加匹配前的纯文本
                if pos < match.start():
                    text = content[pos : match.start()]
                    # 保留文本（包括空白），但跳过完全空的文本
                    if text:
                        components.append(platform_message.Plain(text=text))

                # 处理匹配到的组件
                match_text = match.group(0)
                matched = False
                for pattern, msg_type in patterns:
                    sub_match = re.search(pattern, match_text, re.IGNORECASE)
                    if sub_match:
                        matched = True
                        if msg_type == 'image':
                            img_url = sub_match.group(1)
                            components.append(platform_message.Image(url=img_url))
                        elif msg_type == 'mention':
                            target_id = sub_match.group(1)
                            components.append(platform_message.At(target=str(target_id)))
                        elif msg_type == 'mention_all':
                            components.append(platform_message.AtAll())
                        elif msg_type == 'reply':
                            reply_id = sub_match.group(1)
                            components.append(platform_message.Reply(id=str(reply_id)))
                        elif msg_type == 'quote':
                            quote_id = sub_match.group(1)
                            # Quote requires origin field - use empty list as placeholder
                            components.append(platform_message.Quote(message_id=str(quote_id), origin=[]))
                        elif msg_type == 'emoticon' or msg_type == 'face':
                            emoticon_id = sub_match.group(1)
                            components.append(
                                platform_message.Face(
                                    face_id=str(emoticon_id),
                                    face_name=f'emoticon_{emoticon_id}',
                                )
                            )
                        elif msg_type == 'audio':
                            audio_url = sub_match.group(1)
                            components.append(platform_message.Voice(url=audio_url))
                        elif msg_type == 'video':
                            # 视频作为文件处理
                            video_url = sub_match.group(1)
                            components.append(platform_message.File(url=video_url, name='video'))
                        elif msg_type == 'file':
                            file_url = sub_match.group(1)
                            # 尝试从标签中提取文件名
                            name_match = re.search(r'name=["\']([^"\']*)["\']', match_text, re.IGNORECASE)
                            file_name = name_match.group(1) if name_match else ''
                            components.append(platform_message.File(url=file_url, name=file_name))
                        break

                # 如果没有匹配到任何已知模式，将其作为纯文本
                if not matched:
                    components.append(platform_message.Plain(text=match_text))

                pos = match.end()

            # 添加剩余的文本
            if pos < len(content):
                remaining_text = content[pos:]
                # 保留文本（包括空白），但跳过完全空的文本
                if remaining_text:
                    components.append(platform_message.Plain(text=remaining_text))

        # 如果没有解析出任何组件，但内容不为空，则作为纯文本
        if not components and content:
            components.append(platform_message.Plain(text=content))

        message_chain = platform_message.MessageChain(components)
        await adapter.logger.debug(f'Satori 消息解析完成: 共 {len(components)} 个组件 内容长度={len(content)} 字符')
        return message_chain


class SatoriEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Convert between Satori events and LangBot events"""

    @staticmethod
    def _ensure_string(value: typing.Any, default: str = '') -> str:
        """Ensure value is string type"""
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    async def target2yiri(
        event_data: dict, adapter: 'SatoriAdapter', bot_account_id: str = ''
    ) -> typing.Optional[platform_events.MessageEvent]:
        """Convert Satori event to LangBot event

        This method is used for standalone event conversion.
        Note: The adapter's convert_satori_message method is preferred for better handling.
        """
        event_type = event_data.get('type', '')

        if event_type == 'message-created':
            message = event_data.get('message', {})
            user = event_data.get('user', {})
            guild = event_data.get('guild')
            channel = event_data.get('channel', {})
            login = event_data.get('login', {})

            user_name = SatoriEventConverter._ensure_string(user.get('name') or user.get('nick'), '')
            user_id = SatoriEventConverter._ensure_string(user.get('id'), '')
            message_id = SatoriEventConverter._ensure_string(message.get('id'), '')
            message_content = SatoriEventConverter._ensure_string(message.get('content'), '')

            # Log received message
            await adapter.logger.info(
                f'Satori EventConverter 消息接收: 用户ID={user_id}, 用户名={user_name}, 内容长度={len(message_content)}'
            )

            # Convert message content to MessageChain
            message_chain = await SatoriMessageConverter.target2yiri(
                {'content': message_content}, adapter, bot_account_id
            )

            # Insert Source component at the beginning of the message chain
            message_chain.insert(0, platform_message.Source(id=message_id, time=datetime.datetime.now()))

            # Build original event object for source_platform_object
            original_event = {
                'type': event_type,
                'message': message,
                'user': user,
                'channel': channel,
                'guild': guild,
                'login': login,
            }

            # Try to get timestamp from message or use current time
            msg_timestamp = message.get('timestamp') or message.get('created_at')
            if msg_timestamp:
                try:
                    if isinstance(msg_timestamp, (int, float)):
                        event_time = int(msg_timestamp) if msg_timestamp > 1e12 else int(msg_timestamp * 1000)
                        event_time = event_time // 1000 if event_time > 1e12 else event_time
                    else:
                        # Try parsing ISO format
                        event_time = int(
                            datetime.datetime.fromisoformat(str(msg_timestamp).replace('Z', '+00:00')).timestamp()
                        )
                except (ValueError, TypeError):
                    event_time = int(time.time())
            else:
                event_time = int(time.time())

            # Determine message type based on channel.type or guild presence
            # In Satori protocol:
            # - channel.type = 0: TEXT channel (group/guild message)
            # - channel.type = 1: DIRECT channel (private message)
            channel_type = channel.get('type')
            channel_id = SatoriEventConverter._ensure_string(channel.get('id'), '')

            # Check if it's a private/direct message
            is_private = channel_type == 1

            # Check if it's a group message
            is_group = (guild and guild.get('id')) or (channel_type == 0)

            if is_private:
                # Private/friend message
                sender = platform_entities.Friend(
                    id=user_id,
                    nickname=user_name,
                    remark=user_name,
                )
                friend_message = platform_events.FriendMessage(
                    message_chain=message_chain,
                    sender=sender,
                    time=event_time,
                    source_platform_object=original_event,
                )
                await adapter.logger.info(f'Satori 私聊消息已构建: 用户ID={user_id}, 用户名={user_name}')
                return friend_message
            elif is_group:
                # Group message
                # Use channel.id as group_id (NOT guild.id) to ensure each channel is a unique session
                # This is important for platforms with guild/channel hierarchy (Discord, KOOK, etc.)
                # Using guild.id would incorrectly merge different channels into same session
                group_id = channel_id

                # Build group name: include guild name if available for context
                guild_name = guild.get('name', '') if guild else ''
                channel_name = channel.get('name', '') if channel else ''
                if guild_name and channel_name:
                    group_name = f'{guild_name}#{channel_name}'
                elif guild_name:
                    group_name = guild_name
                elif channel_name:
                    group_name = channel_name
                else:
                    group_name = 'Unknown Group'

                group = platform_entities.Group(
                    id=group_id,
                    name=group_name,
                    permission=platform_entities.Permission.Member,
                )
                sender = platform_entities.GroupMember(
                    id=user_id,
                    member_name=user_name,
                    permission=platform_entities.Permission.Member,
                    group=group,
                    special_title='',
                )
                group_message = platform_events.GroupMessage(
                    message_chain=message_chain,
                    sender=sender,
                    time=event_time,
                    source_platform_object=original_event,
                )
                await adapter.logger.info(f'Satori 群消息已构建: 群ID={group_id}, 发送者={user_name}')
                return group_message
            else:
                # Fallback: treat as private message if cannot determine type
                sender = platform_entities.Friend(
                    id=user_id,
                    nickname=user_name,
                    remark=user_name,
                )
                friend_message = platform_events.FriendMessage(
                    message_chain=message_chain,
                    sender=sender,
                    time=event_time,
                    source_platform_object=original_event,
                )
                await adapter.logger.info(f'Satori 私聊消息已构建 (fallback): 用户ID={user_id}, 用户名={user_name}')
                return friend_message
        return None


class SatoriAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """Satori protocol adapter for LangBot - Native implementation"""

    ws: typing.Optional[typing.Any] = pydantic.Field(exclude=True, default=None)
    session: typing.Optional[aiohttp.ClientSession] = pydantic.Field(exclude=True, default=None)
    running: bool = pydantic.Field(exclude=True, default=False)
    sequence: int = pydantic.Field(exclude=True, default=0)
    logins: typing.List[dict] = pydantic.Field(exclude=True, default_factory=list)
    ready_received: bool = pydantic.Field(exclude=True, default=False)
    heartbeat_task: typing.Optional[asyncio.Task] = pydantic.Field(exclude=True, default=None)
    listeners: typing.Dict[typing.Type, typing.Callable] = pydantic.Field(exclude=True, default_factory=dict)

    message_converter: SatoriMessageConverter = pydantic.Field(default_factory=SatoriMessageConverter)
    event_converter: SatoriEventConverter = pydantic.Field(default_factory=SatoriEventConverter)

    platform: str = pydantic.Field(exclude=True, default='llonebot')
    host: str = pydantic.Field(exclude=True, default='127.0.0.1')
    api_base_url: str = pydantic.Field(exclude=True, default='')
    token: str = pydantic.Field(exclude=True, default='')
    endpoint: str = pydantic.Field(exclude=True, default='')
    port: int = pydantic.Field(exclude=True, default=5600)
    auto_reconnect: bool = pydantic.Field(exclude=True, default=True)
    heartbeat_interval: int = pydantic.Field(exclude=True, default=10)
    reconnect_delay: int = pydantic.Field(exclude=True, default=5)

    def __init__(
        self,
        config: dict,
        logger: abstract_platform_logger.AbstractEventLogger,
    ):
        """Initialize Satori adapter"""
        host = config.get('host', '127.0.0.1')
        port = config.get('port', 5600)

        # 初始化基类
        super().__init__(
            config=config,
            logger=logger,
            platform=config.get('platform', 'llonebot'),
            host=host,
            api_base_url=config.get('satori_api_base_url', f'http://{host}:{port}/v1'),
            token=config.get('token', ''),
            endpoint=config.get('satori_endpoint', f'ws://{host}:{port}/v1/events'),
            auto_reconnect=True,
            port=port,
            heartbeat_interval=10,
            reconnect_delay=5,
        )

    def _is_websocket_closed(self, ws) -> bool:
        """Check if WebSocket connection is closed"""
        if not ws:
            return True
        try:
            if hasattr(ws, 'closed'):
                return ws.closed
            if hasattr(ws, 'close_code'):
                return ws.close_code is not None
            return False
        except AttributeError:
            return True

    async def run(self):
        """Start the adapter"""
        self.running = True
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        retry_count = 0
        max_retries = 10

        await self.logger.info(f'Satori 适配器启动中 - 连接到 {self.endpoint}')

        while self.running:
            try:
                await self.connect_websocket()
                retry_count = 0
            except websockets.exceptions.ConnectionClosed as e:
                await self.logger.warning(f'Satori WebSocket 连接关闭: {e}')
                retry_count += 1
            except Exception as e:
                await self.logger.error(f'Satori WebSocket 连接失败: {e}')
                retry_count += 1

            if not self.running:
                break

            if retry_count >= max_retries:
                await self.logger.error(f'达到最大重试次数 ({max_retries})，停止重试')
                break

            if not self.auto_reconnect:
                break

            delay = min(self.reconnect_delay * (2 ** (retry_count - 1)), 60)
            await self.logger.info(f'{delay}秒后重新连接...')
            await asyncio.sleep(delay)

        if self.session:
            await self.session.close()

    async def connect_websocket(self):
        """Connect to WebSocket"""
        await self.logger.info(f'Satori 正在连接到 WebSocket: {self.endpoint}')
        await self.logger.info(f'Satori HTTP API 地址: {self.api_base_url}')

        if not self.endpoint.startswith(('ws://', 'wss://')):
            raise ValueError(f'WebSocket URL必须以ws://或wss://开头: {self.endpoint}')

        try:
            self.ws = await websockets.connect(self.endpoint)
            await asyncio.sleep(0.1)

            await self.send_identify()

            # Cancel any existing heartbeat task before creating a new one
            # to avoid race condition on rapid reconnection
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

            async for message in self.ws:
                try:
                    await self.handle_message(message)
                except Exception as e:
                    await self.logger.error(f'Satori 处理消息异常: {e}')

        except websockets.exceptions.ConnectionClosed as e:
            await self.logger.warning(f'Satori WebSocket 连接关闭: {e}')
            raise
        except Exception as e:
            await self.logger.error(f'Satori WebSocket 连接异常: {e}')
            raise
        finally:
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            if self.ws:
                try:
                    await self.ws.close()
                except Exception as e:
                    await self.logger.error(f'Satori WebSocket 关闭异常: {e}')

    async def send_identify(self):
        """Send IDENTIFY signal"""
        if not self.ws:
            raise Exception('WebSocket连接未建立')

        if self._is_websocket_closed(self.ws):
            raise Exception('WebSocket连接已关闭')

        identify_payload = {
            'op': 3,  # IDENTIFY
            'body': {
                'token': str(self.token) if self.token else '',
            },
        }

        if self.sequence > 0:
            identify_payload['body']['sn'] = self.sequence

        try:
            message_str = json.dumps(identify_payload, ensure_ascii=False)
            await self.ws.send(message_str)
            await self.logger.info('Satori IDENTIFY 信令已发送')
        except Exception as e:
            await self.logger.error(f'发送 IDENTIFY 信令失败: {e}')
            raise

    async def heartbeat_loop(self):
        """Heartbeat loop"""
        try:
            while self.running and self.ws:
                await asyncio.sleep(self.heartbeat_interval)

                if self.ws and not self._is_websocket_closed(self.ws):
                    try:
                        ping_payload = {
                            'op': 1,  # PING
                            'body': {},
                        }
                        await self.ws.send(json.dumps(ping_payload, ensure_ascii=False))
                    except Exception as e:
                        await self.logger.error(f'Satori WebSocket 发送心跳失败: {e}')
                        break
                else:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.logger.error(f'心跳任务异常: {e}')

    async def handle_message(self, message: str):
        """Handle WebSocket message"""
        try:
            data = json.loads(message)
            op = data.get('op')
            body = data.get('body', {})

            if op == 4:  # READY
                self.logins = body.get('logins', [])
                self.ready_received = True

                if self.logins:
                    for i, login in enumerate(self.logins):
                        platform = login.get('platform', '')
                        user = login.get('user', {})
                        user_id = user.get('id', '')
                        user_name = user.get('name', '')
                        await self.logger.info(
                            f'Satori 连接成功 - Bot {i + 1}: platform={platform}, user_id={user_id}, user_name={user_name}'
                        )

                if 'sn' in body:
                    self.sequence = body['sn']

            elif op == 2:  # PONG
                pass

            elif op == 0:  # EVENT
                await self.handle_event(body)
                if 'sn' in body:
                    self.sequence = body['sn']

            elif op == 5:  # META
                if 'sn' in body:
                    self.sequence = body['sn']

        except json.JSONDecodeError as e:
            await self.logger.error(f'解析 WebSocket 消息失败: {e}, 消息内容: {message}')
        except Exception as e:
            await self.logger.error(f'处理 WebSocket 消息异常: {e}')

    async def handle_event(self, event_data: dict):
        """Handle event"""
        try:
            event_type = event_data.get('type')

            if event_type == 'message-created':
                message = event_data.get('message', {})
                user = event_data.get('user', {})
                channel = event_data.get('channel', {})
                guild = event_data.get('guild')
                login = event_data.get('login', {})

                # Skip messages from self
                bot_user_id = login.get('user', {}).get('id')
                msg_user_id = user.get('id')
                if bot_user_id and msg_user_id and str(bot_user_id) == str(msg_user_id):
                    return

                lb_event = await self.convert_satori_message(message, user, channel, guild, login)
                if lb_event and type(lb_event) in self.listeners:
                    await self.listeners[type(lb_event)](lb_event, self)

        except Exception as e:
            await self.logger.error(f'处理事件失败: {e}\n{traceback.format_exc()}')

    async def convert_satori_message(
        self,
        message: dict,
        user: dict,
        channel: dict,
        guild: typing.Optional[dict],
        login: dict,
    ) -> typing.Optional[platform_events.MessageEvent]:
        """Convert Satori message to LangBot event

        This is the main method for converting Satori messages to LangBot events.
        It handles both private and group messages based on channel.type and guild info.
        """
        try:
            # Extract basic info with type safety
            user_id = str(user.get('id', '') or '')
            user_name = str(user.get('name', '') or user.get('nick', '') or '')
            message_id = str(message.get('id', '') or '')
            message_content = str(message.get('content', '') or '')

            # Log received message (truncate long content for debug preview)
            log_content = message_content[:100] + '...' if len(message_content) > 100 else message_content
            # At info level, avoid logging raw content to protect privacy and reduce log volume
            await self.logger.info(
                f'Satori 消息接收: 用户ID={user_id}, 用户名={user_name}, 内容长度={len(message_content)}, 消息ID={message_id}'
            )
            # Detailed content preview only at debug level
            await self.logger.debug(f"Satori 消息内容预览: 用户ID={user_id}, 消息ID={message_id}, 预览='{log_content}'")

            # Convert message content
            message_chain = await SatoriMessageConverter.target2yiri({'content': message_content}, self, '')

            # Insert Source component at the beginning of the message chain
            message_chain.insert(0, platform_message.Source(id=message_id, time=datetime.datetime.now()))

            # Build original event object for source_platform_object
            original_event = {
                'type': 'message-created',
                'message': message,
                'user': user,
                'channel': channel,
                'guild': guild,
                'login': login,
            }

            # Try to get timestamp from message or use current time
            msg_timestamp = message.get('timestamp') or message.get('created_at')
            if msg_timestamp:
                try:
                    if isinstance(msg_timestamp, (int, float)):
                        # Handle milliseconds vs seconds
                        event_time = int(msg_timestamp) if msg_timestamp < 1e12 else int(msg_timestamp / 1000)
                    else:
                        # Try parsing ISO format
                        event_time = int(
                            datetime.datetime.fromisoformat(str(msg_timestamp).replace('Z', '+00:00')).timestamp()
                        )
                except (ValueError, TypeError):
                    event_time = int(time.time())
            else:
                event_time = int(time.time())

            # Determine message type based on channel.type or guild presence
            # In Satori protocol:
            # - channel.type = 0: TEXT channel (group/guild message)
            # - channel.type = 1: DIRECT channel (private message)
            # Some implementations (like LLOneBot) may not provide guild info for group chats
            channel_type = channel.get('type')
            channel_id = str(channel.get('id', '') or '')

            # Check if it's a private/direct message
            # Private message: channel.type == 1, or no guild and no channel type (legacy)
            is_private = channel_type == 1

            # Check if it's a group message
            # Group message: has guild info, or channel.type == 0
            is_group = (guild and guild.get('id')) or (channel_type == 0)

            if is_private:
                # Private/friend message
                sender = platform_entities.Friend(
                    id=user_id,
                    nickname=user_name,
                    remark=user_name,
                )
                friend_message = platform_events.FriendMessage(
                    message_chain=message_chain,
                    sender=sender,
                    time=event_time,
                    source_platform_object=original_event,
                )
                await self.logger.debug(
                    f'Satori 私聊消息已构建: 用户ID={user_id}, 用户名={user_name}, 组件数={len(message_chain)}'
                )
                return friend_message
            elif is_group:
                # Group message
                # Use channel.id as group_id (NOT guild.id) to ensure each channel is a unique session
                # This is important for platforms with guild/channel hierarchy (Discord, KOOK, etc.)
                # Using guild.id would incorrectly merge different channels into same session
                group_id = channel_id

                # Build group name: include guild name if available for context
                guild_name = str(guild.get('name', '') if guild else '')
                channel_name = str(channel.get('name', '') if channel else '')
                if guild_name and channel_name:
                    group_name = f'{guild_name}#{channel_name}'
                elif guild_name:
                    group_name = guild_name
                elif channel_name:
                    group_name = channel_name
                else:
                    group_name = 'Unknown Group'

                group = platform_entities.Group(
                    id=group_id,
                    name=group_name,
                    permission=platform_entities.Permission.Member,
                )
                sender = platform_entities.GroupMember(
                    id=user_id,
                    member_name=user_name,
                    permission=platform_entities.Permission.Member,
                    group=group,
                    special_title='',
                )
                group_message = platform_events.GroupMessage(
                    message_chain=message_chain,
                    sender=sender,
                    time=event_time,
                    source_platform_object=original_event,
                )
                await self.logger.debug(
                    f'Satori 群消息已构建: 群ID={group_id}, 发送者={user_name}, 组件数={len(message_chain)}'
                )
                return group_message
            else:
                # Fallback: treat as private message if cannot determine type
                await self.logger.warning(f'Satori 无法确定消息类型，使用私聊作为fallback: channel_type={channel_type}')
                sender = platform_entities.Friend(
                    id=user_id,
                    nickname=user_name,
                    remark=user_name,
                )
                friend_message = platform_events.FriendMessage(
                    message_chain=message_chain,
                    sender=sender,
                    time=event_time,
                    source_platform_object=original_event,
                )
                await self.logger.info(f'Satori 私聊消息已构建 (fallback): 用户ID={user_id}, 用户名={user_name}')
                return friend_message

        except Exception as e:
            await self.logger.error(f'转换 Satori 消息失败: {e}\n{traceback.format_exc()}')
            return None

    async def send_http_request(
        self,
        method: str,
        path: str,
        data: typing.Optional[dict] = None,
        platform: typing.Optional[str] = None,
        user_id: typing.Optional[str] = None,
    ) -> typing.Optional[dict]:
        """Send HTTP request to Satori API"""
        if not self.session:
            await self.logger.error('HTTP session 未初始化')
            return None

        url = f'{self.api_base_url}{path}'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',
        }

        if platform:
            headers['Satori-Platform'] = platform
        if user_id:
            headers['Satori-User-ID'] = user_id

        try:
            async with self.session.request(method, url, headers=headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    text = await response.text()
                    await self.logger.error(f'Satori API 请求失败: {response.status} - {text}')
                    return None
        except Exception as e:
            await self.logger.error(f'Satori API 请求异常: {e}')
            return None

    async def upload_image(
        self,
        image_bytes: bytes,
        mime_type: str = 'image/png',
    ) -> typing.Optional[str]:
        """Upload image to Satori server and return the URL

        Uses multipart/form-data to upload the image file via upload.create API.
        Returns the URL of the uploaded image, or None if upload fails.
        """
        if not self.session:
            await self.logger.error('HTTP session 未初始化')
            return None

        url = f'{self.api_base_url}/upload.create'
        headers = {}

        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        platform = ''
        user_id = ''
        if self.logins:
            current_login = self.logins[0]
            platform = current_login.get('platform', '')
            user = current_login.get('user', {})
            user_id = user.get('id', '')

        if platform:
            headers['Satori-Platform'] = platform
        if user_id:
            headers['Satori-User-ID'] = user_id

        try:
            # Determine file extension from mime type
            ext = 'png'
            if 'jpeg' in mime_type or 'jpg' in mime_type:
                ext = 'jpg'
            elif 'gif' in mime_type:
                ext = 'gif'
            elif 'webp' in mime_type:
                ext = 'webp'

            # Create multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field('file', image_bytes, filename=f'image.{ext}', content_type=mime_type)

            async with self.session.post(url, headers=headers, data=form_data) as response:
                if response.status == 200:
                    result = await response.json()
                    # The response should contain the URL of the uploaded file
                    if isinstance(result, dict) and 'url' in result:
                        return result['url']
                    elif isinstance(result, list) and len(result) > 0 and 'url' in result[0]:
                        return result[0]['url']
                    else:
                        await self.logger.warning(f'Satori 图片上传响应格式未知: {result}')
                        return None
                else:
                    text = await response.text()
                    await self.logger.error(f'Satori 图片上传失败: {response.status} - {text}')
                    return None
        except Exception as e:
            await self.logger.error(f'Satori 图片上传异常: {e}')
            return None

    async def kill(self) -> bool:
        """Stop the adapter"""
        self.running = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.session:
            await self.session.close()
        await self.logger.info('Satori 适配器已停止')
        return True

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ):
        """Send message

        Args:
            target_type: Message target type ('group' for channels, 'person' for DM)
            target_id: For 'group': channel_id. For 'person': user_id (will create DM channel first)
            message: Message content to send

        Note:
            - For group messages: target_id should be channel_id (NOT guild_id)
            - For private messages: target_id should be user_id, DM channel will be created automatically
        """
        try:
            content = await self.message_converter.yiri2target(message, self)

            platform = ''
            bot_user_id = ''
            if self.logins:
                current_login = self.logins[0]
                platform = current_login.get('platform', '')
                user = current_login.get('user', {})
                bot_user_id = user.get('id', '')

            channel_id = ''

            if target_type == 'group':
                # For group/channel messages, target_id is channel_id directly
                channel_id = target_id
            elif target_type == 'person':
                # For private/DM messages, need to create DM channel first using user.channel.create
                # Satori protocol requires creating a private channel with the user
                dm_data = {'user_id': target_id}
                dm_result = await self.send_http_request('POST', '/user.channel.create', dm_data, platform, bot_user_id)
                if dm_result and dm_result.get('id'):
                    channel_id = dm_result.get('id')
                    await self.logger.debug(f'Satori 已创建私聊频道: user_id={target_id}, channel_id={channel_id}')
                else:
                    await self.logger.error(f'Satori 创建私聊频道失败: user_id={target_id}, response={dm_result}')
                    return
            else:
                # Unknown target_type - log error and attempt to use target_id as channel_id
                await self.logger.warning(
                    f"Satori send_message: 未知的 target_type='{target_type}'，将尝试使用 target_id 作为 channel_id"
                )
                channel_id = target_id

            if not channel_id:
                await self.logger.error(
                    f'Satori send_message: 无法确定 channel_id (target_type={target_type}, target_id={target_id})'
                )
                return

            data = {'channel_id': channel_id, 'content': content}
            await self.send_http_request('POST', '/message.create', data, platform, bot_user_id)

        except Exception as e:
            await self.logger.error(f'Satori 发送消息失败: {e}')

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Reply to message"""
        try:
            content = await self.message_converter.yiri2target(message, self)

            # Try to get channel_id from source_platform_object first (Satori protocol needs original channel.id)
            channel_id = ''
            original_message_id = ''
            if hasattr(message_source, 'source_platform_object') and message_source.source_platform_object:
                source_obj = message_source.source_platform_object
                if isinstance(source_obj, dict):
                    channel = source_obj.get('channel', {})
                    if channel and channel.get('id'):
                        channel_id = str(channel.get('id'))
                    # Get original message ID for quoting (Satori protocol)
                    msg_obj = source_obj.get('message', {})
                    if msg_obj and msg_obj.get('id'):
                        original_message_id = str(msg_obj.get('id'))

            # Fallback: get channel_id from message source
            if not channel_id:
                if isinstance(message_source, platform_events.GroupMessage):
                    # Group message: use group ID
                    if hasattr(message_source.sender, 'group') and hasattr(message_source.sender.group, 'id'):
                        channel_id = message_source.sender.group.id
                elif isinstance(message_source, platform_events.FriendMessage):
                    # Private message: use sender ID as channel_id
                    if hasattr(message_source.sender, 'id'):
                        channel_id = message_source.sender.id

            # Last fallback
            if not channel_id:
                if hasattr(message_source, 'sender') and hasattr(message_source.sender, 'id'):
                    channel_id = message_source.sender.id

            if not channel_id:
                await self.logger.error('无法获取频道ID')
                return

            # Handle quote_origin: prepend <quote /> element per Satori protocol
            if quote_origin:
                if original_message_id:
                    # Prepend quote element before content per Satori protocol
                    content = f'<quote id="{original_message_id}"/>{content}'
                    await self.logger.debug(f'Satori 引用消息: message_id={original_message_id}')
                else:
                    # quote_origin requested but message ID not available - log and proceed without quote
                    await self.logger.warning('Satori quote_origin=True 但无法获取原消息ID，将不使用引用发送')

            platform = ''
            user_id = ''
            if self.logins:
                current_login = self.logins[0]
                platform = current_login.get('platform', '')
                user = current_login.get('user', {})
                user_id = user.get('id', '')

            data = {'channel_id': channel_id, 'content': content}
            await self.send_http_request('POST', '/message.create', data, platform, user_id)

        except Exception as e:
            await self.logger.error(f'Satori 回复消息失败: {e}')

    async def is_muted(self, group_id: int) -> bool:
        """Check if the bot is muted in a group"""
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [
                platform_events.Event,
                abstract_platform_adapter.AbstractMessagePlatformAdapter,
            ],
            None,
        ],
    ):
        """Register an event listener"""
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [
                platform_events.Event,
                abstract_platform_adapter.AbstractMessagePlatformAdapter,
            ],
            None,
        ],
    ):
        """Unregister an event listener"""
        if event_type in self.listeners:
            del self.listeners[event_type]

    async def run_async(self):
        """Async run wrapper"""
        await self.run()
