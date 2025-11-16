from __future__ import annotations

import discord

import typing
import re
import base64
import uuid
import os
import datetime
import asyncio
from enum import Enum

import aiohttp
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from ..logger import EventLogger


# 语音功能相关异常定义
class VoiceConnectionError(Exception):
    """语音连接基础异常"""

    def __init__(self, message: str, error_code: str = None, guild_id: int = None):
        super().__init__(message)
        self.error_code = error_code
        self.guild_id = guild_id
        self.timestamp = datetime.datetime.now()


class VoicePermissionError(VoiceConnectionError):
    """语音权限异常"""

    def __init__(self, message: str, missing_permissions: list = None, user_id: int = None, channel_id: int = None):
        super().__init__(message, 'PERMISSION_ERROR')
        self.missing_permissions = missing_permissions or []
        self.user_id = user_id
        self.channel_id = channel_id


class VoiceNetworkError(VoiceConnectionError):
    """语音网络异常"""

    def __init__(self, message: str, retry_count: int = 0):
        super().__init__(message, 'NETWORK_ERROR')
        self.retry_count = retry_count
        self.last_attempt = datetime.datetime.now()


class VoiceConnectionStatus(Enum):
    """语音连接状态枚举"""

    IDLE = 'idle'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    PLAYING = 'playing'
    RECONNECTING = 'reconnecting'
    FAILED = 'failed'


class VoiceConnectionInfo:
    """
    语音连接信息类

    用于存储和管理单个语音连接的详细信息，包括连接状态、时间戳、
    频道信息等。提供连接信息的标准化数据结构。

    @author: @ydzat
    @version: 1.0
    @since: 2025-07-04
    """

    def __init__(self, guild_id: int, channel_id: int, channel_name: str = None):
        """
        初始化语音连接信息

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID
            channel_id (int): 语音频道ID
            channel_name (str, optional): 语音频道名称
        """
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.channel_name = channel_name or f'Channel-{channel_id}'
        self.connected = False
        self.connection_time: datetime.datetime = None
        self.last_activity = datetime.datetime.now()
        self.status = VoiceConnectionStatus.IDLE
        self.user_count = 0
        self.latency = 0.0
        self.connection_health = 'unknown'
        self.voice_client = None

    def update_status(self, status: VoiceConnectionStatus):
        """
        更新连接状态

        @author: @ydzat

        Args:
            status (VoiceConnectionStatus): 新的连接状态
        """
        self.status = status
        self.last_activity = datetime.datetime.now()

        if status == VoiceConnectionStatus.CONNECTED:
            self.connected = True
            if self.connection_time is None:
                self.connection_time = datetime.datetime.now()
        elif status in [VoiceConnectionStatus.IDLE, VoiceConnectionStatus.FAILED]:
            self.connected = False
            self.connection_time = None
            self.voice_client = None

    def to_dict(self) -> dict:
        """
        转换为字典格式

        @author: @ydzat

        Returns:
            dict: 连接信息的字典表示
        """
        return {
            'guild_id': self.guild_id,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'connected': self.connected,
            'connection_time': self.connection_time.isoformat() if self.connection_time else None,
            'last_activity': self.last_activity.isoformat(),
            'status': self.status.value,
            'user_count': self.user_count,
            'latency': self.latency,
            'connection_health': self.connection_health,
        }


class VoiceConnectionManager:
    """
    语音连接管理器

    负责管理多个服务器的语音连接，提供连接建立、断开、状态查询等功能。
    采用单例模式确保全局只有一个连接管理器实例。

    @author: @ydzat
    @version: 1.0
    @since: 2025-07-04
    """

    def __init__(self, bot: discord.Client, logger: EventLogger):
        """
        初始化语音连接管理器

        @author: @ydzat

        Args:
            bot (discord.Client): Discord 客户端实例
            logger (EventLogger): 事件日志记录器
        """
        self.bot = bot
        self.logger = logger
        self.connections: typing.Dict[int, VoiceConnectionInfo] = {}
        self._connection_lock = asyncio.Lock()
        self._cleanup_task = None
        self._monitoring_enabled = True

    async def join_voice_channel(self, guild_id: int, channel_id: int, user_id: int = None) -> discord.VoiceClient:
        """
        加入语音频道

        验证用户权限和频道状态后，建立到指定语音频道的连接。
        支持连接复用和自动重连机制。

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID
            channel_id (int): 语音频道ID
            user_id (int, optional): 请求用户ID，用于权限验证

        Returns:
            discord.VoiceClient: 语音客户端实例

        Raises:
            VoicePermissionError: 权限不足时抛出
            VoiceNetworkError: 网络连接失败时抛出
            VoiceConnectionError: 其他连接错误时抛出
        """
        async with self._connection_lock:
            try:
                # 获取服务器和频道对象
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    raise VoiceConnectionError(f'无法找到服务器 {guild_id}', 'GUILD_NOT_FOUND', guild_id)

                channel = guild.get_channel(channel_id)
                if not channel or not isinstance(channel, discord.VoiceChannel):
                    raise VoiceConnectionError(f'无法找到语音频道 {channel_id}', 'CHANNEL_NOT_FOUND', guild_id)

                # 验证用户是否在语音频道中（如果提供了用户ID）
                if user_id:
                    await self._validate_user_in_channel(guild, channel, user_id)

                # 验证机器人权限
                await self._validate_bot_permissions(channel)

                # 检查是否已有连接
                if guild_id in self.connections:
                    existing_conn = self.connections[guild_id]
                    if existing_conn.connected and existing_conn.voice_client:
                        if existing_conn.channel_id == channel_id:
                            # 已连接到相同频道，返回现有连接
                            await self.logger.info(f'复用现有语音连接: {guild.name} -> {channel.name}')
                            return existing_conn.voice_client
                        else:
                            # 连接到不同频道，先断开旧连接
                            await self._disconnect_internal(guild_id)

                # 建立新连接
                voice_client = await channel.connect()

                # 更新连接信息
                conn_info = VoiceConnectionInfo(guild_id, channel_id, channel.name)
                conn_info.voice_client = voice_client
                conn_info.update_status(VoiceConnectionStatus.CONNECTED)
                conn_info.user_count = len(channel.members)
                self.connections[guild_id] = conn_info

                await self.logger.info(f'成功连接到语音频道: {guild.name} -> {channel.name}')
                return voice_client

            except discord.ClientException as e:
                raise VoiceNetworkError(f'Discord 客户端错误: {str(e)}')
            except discord.opus.OpusNotLoaded as e:
                raise VoiceConnectionError(f'Opus 编码器未加载: {str(e)}', 'OPUS_NOT_LOADED', guild_id)
            except Exception as e:
                await self.logger.error(f'连接语音频道时发生未知错误: {str(e)}')
                raise VoiceConnectionError(f'连接失败: {str(e)}', 'UNKNOWN_ERROR', guild_id)

    async def leave_voice_channel(self, guild_id: int) -> bool:
        """
        离开语音频道

        断开指定服务器的语音连接，清理相关资源和状态信息。
        确保音频播放停止后再断开连接。

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID

        Returns:
            bool: 断开是否成功
        """
        async with self._connection_lock:
            return await self._disconnect_internal(guild_id)

    async def _disconnect_internal(self, guild_id: int) -> bool:
        """
        内部断开连接方法

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID

        Returns:
            bool: 断开是否成功
        """
        if guild_id not in self.connections:
            return True

        conn_info = self.connections[guild_id]

        try:
            if conn_info.voice_client and conn_info.voice_client.is_connected():
                # 停止当前播放
                if conn_info.voice_client.is_playing():
                    conn_info.voice_client.stop()

                # 等待播放完全停止
                await asyncio.sleep(0.1)

                # 断开连接
                await conn_info.voice_client.disconnect()

            conn_info.update_status(VoiceConnectionStatus.IDLE)
            del self.connections[guild_id]

            await self.logger.info(f'已断开语音连接: Guild {guild_id}')
            return True

        except Exception as e:
            await self.logger.error(f'断开语音连接时发生错误: {str(e)}')
            # 即使出错也要清理连接记录
            conn_info.update_status(VoiceConnectionStatus.FAILED)
            if guild_id in self.connections:
                del self.connections[guild_id]
            return False

    async def get_voice_client(self, guild_id: int) -> typing.Optional[discord.VoiceClient]:
        """
        获取语音客户端

        返回指定服务器的语音客户端实例，如果未连接则返回 None。
        会验证连接的有效性，自动清理无效连接。

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID

        Returns:
            Optional[discord.VoiceClient]: 语音客户端实例或 None
        """
        if guild_id not in self.connections:
            return None

        conn_info = self.connections[guild_id]

        # 验证连接是否仍然有效
        if conn_info.voice_client and not conn_info.voice_client.is_connected():
            # 连接已失效，清理状态
            await self._disconnect_internal(guild_id)
            return None

        return conn_info.voice_client if conn_info.connected else None

    async def is_connected_to_voice(self, guild_id: int) -> bool:
        """
        检查是否连接到语音频道

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID

        Returns:
            bool: 是否已连接
        """
        if guild_id not in self.connections:
            return False

        conn_info = self.connections[guild_id]

        # 检查实际连接状态
        if conn_info.voice_client and not conn_info.voice_client.is_connected():
            # 连接已失效，清理状态
            await self._disconnect_internal(guild_id)
            return False

        return conn_info.connected

    async def get_connection_status(self, guild_id: int) -> typing.Optional[dict]:
        """
        获取连接状态信息

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID

        Returns:
            Optional[dict]: 连接状态信息字典或 None
        """
        if guild_id not in self.connections:
            return None

        conn_info = self.connections[guild_id]

        # 更新实时信息
        if conn_info.voice_client and conn_info.voice_client.is_connected():
            conn_info.latency = conn_info.voice_client.latency * 1000  # 转换为毫秒
            conn_info.connection_health = 'good' if conn_info.latency < 100 else 'poor'

            # 更新频道用户数
            guild = self.bot.get_guild(guild_id)
            if guild:
                channel = guild.get_channel(conn_info.channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    conn_info.user_count = len(channel.members)

        return conn_info.to_dict()

    async def list_active_connections(self) -> typing.List[dict]:
        """
        列出所有活跃连接

        @author: @ydzat

        Returns:
            List[dict]: 活跃连接列表
        """
        active_connections = []

        for guild_id, conn_info in self.connections.items():
            if conn_info.connected:
                status = await self.get_connection_status(guild_id)
                if status:
                    active_connections.append(status)

        return active_connections

    async def get_voice_channel_info(self, guild_id: int, channel_id: int) -> typing.Optional[dict]:
        """
        获取语音频道信息

        @author: @ydzat

        Args:
            guild_id (int): 服务器ID
            channel_id (int): 频道ID

        Returns:
            Optional[dict]: 频道信息字典或 None
        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return None

        # 获取用户信息
        users = []
        for member in channel.members:
            users.append(
                {'id': member.id, 'name': member.display_name, 'status': str(member.status), 'is_bot': member.bot}
            )

        # 获取权限信息
        bot_member = guild.me
        permissions = channel.permissions_for(bot_member)

        return {
            'channel_id': channel_id,
            'channel_name': channel.name,
            'guild_id': guild_id,
            'guild_name': guild.name,
            'user_limit': channel.user_limit,
            'current_users': users,
            'user_count': len(users),
            'bitrate': channel.bitrate,
            'permissions': {
                'connect': permissions.connect,
                'speak': permissions.speak,
                'use_voice_activation': permissions.use_voice_activation,
                'priority_speaker': permissions.priority_speaker,
            },
        }

    async def _validate_user_in_channel(self, guild: discord.Guild, channel: discord.VoiceChannel, user_id: int):
        """
        验证用户是否在语音频道中

        @author: @ydzat

        Args:
            guild: Discord 服务器对象
            channel: 语音频道对象
            user_id: 用户ID

        Raises:
            VoicePermissionError: 用户不在频道中时抛出
        """
        member = guild.get_member(user_id)
        if not member:
            raise VoicePermissionError(f'无法找到用户 {user_id}', ['member_not_found'], user_id, channel.id)

        if not member.voice or member.voice.channel != channel:
            raise VoicePermissionError(
                f'用户 {member.display_name} 不在语音频道 {channel.name} 中',
                ['user_not_in_channel'],
                user_id,
                channel.id,
            )

    async def _validate_bot_permissions(self, channel: discord.VoiceChannel):
        """
        验证机器人权限

        @author: @ydzat

        Args:
            channel: 语音频道对象

        Raises:
            VoicePermissionError: 权限不足时抛出
        """
        bot_member = channel.guild.me
        permissions = channel.permissions_for(bot_member)

        missing_permissions = []

        if not permissions.connect:
            missing_permissions.append('connect')
        if not permissions.speak:
            missing_permissions.append('speak')

        if missing_permissions:
            raise VoicePermissionError(
                f'机器人在频道 {channel.name} 中缺少权限: {", ".join(missing_permissions)}',
                missing_permissions,
                channel_id=channel.id,
            )

    async def cleanup_inactive_connections(self):
        """
        清理无效连接

        定期检查并清理已断开或无效的语音连接，释放资源。

        @author: @ydzat
        """
        cleanup_guilds = []

        for guild_id, conn_info in self.connections.items():
            if not conn_info.voice_client or not conn_info.voice_client.is_connected():
                cleanup_guilds.append(guild_id)

        for guild_id in cleanup_guilds:
            await self._disconnect_internal(guild_id)

        if cleanup_guilds:
            await self.logger.info(f'清理了 {len(cleanup_guilds)} 个无效的语音连接')

    async def start_monitoring(self):
        """
        开始连接监控

        @author: @ydzat
        """
        if self._cleanup_task is None and self._monitoring_enabled:
            self._cleanup_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """
        停止连接监控

        @author: @ydzat
        """
        self._monitoring_enabled = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _monitoring_loop(self):
        """
        监控循环

        @author: @ydzat
        """
        try:
            while self._monitoring_enabled:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self.cleanup_inactive_connections()
        except asyncio.CancelledError:
            pass

    async def disconnect_all(self):
        """
        断开所有连接

        @author: @ydzat
        """
        async with self._connection_lock:
            guild_ids = list(self.connections.keys())
            for guild_id in guild_ids:
                await self._disconnect_internal(guild_id)

        await self.stop_monitoring()


class DiscordMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
    ) -> typing.Tuple[str, typing.List[discord.File]]:
        for ele in message_chain:
            if isinstance(ele, platform_message.At):
                message_chain.remove(ele)
                break

        text_string = ''
        image_files = []

        for ele in message_chain:
            if isinstance(ele, platform_message.Image):
                image_bytes = None
                filename = f'{uuid.uuid4()}.png'  # 默认文件名

                if ele.base64:
                    # 处理base64编码的图片
                    if ele.base64.startswith('data:'):
                        # 从data URL中提取文件类型
                        data_header = ele.base64.split(',')[0]
                        if 'jpeg' in data_header or 'jpg' in data_header:
                            filename = f'{uuid.uuid4()}.jpg'
                        elif 'gif' in data_header:
                            filename = f'{uuid.uuid4()}.gif'
                        elif 'webp' in data_header:
                            filename = f'{uuid.uuid4()}.webp'
                        # 去掉data:image/xxx;base64,前缀
                        base64_data = ele.base64.split(',')[1]
                    else:
                        base64_data = ele.base64
                    image_bytes = base64.b64decode(base64_data)
                elif ele.url:
                    # 从URL下载图片
                    async with aiohttp.ClientSession() as session:
                        async with session.get(ele.url) as response:
                            image_bytes = await response.read()
                            # 从URL或Content-Type推断文件类型
                            content_type = response.headers.get('Content-Type', '')
                            if 'jpeg' in content_type or 'jpg' in content_type:
                                filename = f'{uuid.uuid4()}.jpg'
                            elif 'gif' in content_type:
                                filename = f'{uuid.uuid4()}.gif'
                            elif 'webp' in content_type:
                                filename = f'{uuid.uuid4()}.webp'
                            elif ele.url.lower().endswith(('.jpg', '.jpeg')):
                                filename = f'{uuid.uuid4()}.jpg'
                            elif ele.url.lower().endswith('.gif'):
                                filename = f'{uuid.uuid4()}.gif'
                            elif ele.url.lower().endswith('.webp'):
                                filename = f'{uuid.uuid4()}.webp'
                elif ele.path:
                    # 从文件路径读取图片
                    # 确保路径没有空字节
                    clean_path = ele.path.replace('\x00', '')
                    clean_path = os.path.abspath(clean_path)

                    if not os.path.exists(clean_path):
                        continue  # 跳过不存在的文件

                    try:
                        with open(clean_path, 'rb') as f:
                            image_bytes = f.read()
                        # 从文件路径获取文件名，保持原始扩展名
                        original_filename = os.path.basename(clean_path)
                        if original_filename and '.' in original_filename:
                            # 保持原始文件名的扩展名
                            ext = original_filename.split('.')[-1].lower()
                            filename = f'{uuid.uuid4()}.{ext}'
                        else:
                            # 如果没有扩展名，尝试从文件内容检测
                            if image_bytes.startswith(b'\xff\xd8\xff'):
                                filename = f'{uuid.uuid4()}.jpg'
                            elif image_bytes.startswith(b'GIF'):
                                filename = f'{uuid.uuid4()}.gif'
                            elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:20]:
                                filename = f'{uuid.uuid4()}.webp'
                            # 默认保持PNG
                    except Exception as e:
                        print(f'Error reading image file {clean_path}: {e}')
                        continue  # 跳过读取失败的文件

                if image_bytes:
                    # 使用BytesIO创建文件对象，避免路径问题
                    import io

                    image_files.append(discord.File(fp=io.BytesIO(image_bytes), filename=filename))
            elif isinstance(ele, platform_message.Plain):
                text_string += ele.text
            elif isinstance(ele, platform_message.Forward):
                for node in ele.node_list:
                    (
                        node_text,
                        node_images,
                    ) = await DiscordMessageConverter.yiri2target(node.message_chain)
                    text_string += node_text
                    image_files.extend(node_images)

        return text_string, image_files

    @staticmethod
    async def target2yiri(message: discord.Message) -> platform_message.MessageChain:
        lb_msg_list = []

        msg_create_time = datetime.datetime.fromtimestamp(int(message.created_at.timestamp()))

        lb_msg_list.append(platform_message.Source(id=message.id, time=msg_create_time))

        element_list = []

        def text_element_recur(
            text_ele: str,
        ) -> list[platform_message.MessageComponent]:
            if text_ele == '':
                return []

            # <@1234567890>
            # @everyone
            # @here
            at_pattern = re.compile(r'(@everyone|@here|<@[\d]+>)')
            at_matches = at_pattern.findall(text_ele)

            if len(at_matches) > 0:
                mid_at = at_matches[0]

                text_split = text_ele.split(mid_at)

                mid_at_component = []

                if mid_at == '@everyone' or mid_at == '@here':
                    mid_at_component.append(platform_message.AtAll())
                else:
                    mid_at_component.append(platform_message.At(target=mid_at[2:-1]))

                return text_element_recur(text_split[0]) + mid_at_component + text_element_recur(text_split[1])
            else:
                return [platform_message.Plain(text=text_ele)]

        element_list.extend(text_element_recur(message.content))

        # attachments
        for attachment in message.attachments:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(attachment.url) as response:
                    image_data = await response.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                    image_format = response.headers['Content-Type']
                    element_list.append(platform_message.Image(base64=f'data:{image_format};base64,{image_base64}'))

        return platform_message.MessageChain(element_list)


class DiscordEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> discord.Message:
        pass

    @staticmethod
    async def target2yiri(event: discord.Message) -> platform_events.Event:
        message_chain = await DiscordMessageConverter.target2yiri(event)

        if isinstance(event.channel, discord.DMChannel):
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.author.id,
                    nickname=event.author.name,
                    remark=event.channel.id,
                ),
                message_chain=message_chain,
                time=event.created_at.timestamp(),
                source_platform_object=event,
            )
        elif isinstance(event.channel, discord.TextChannel):
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.author.id,
                    member_name=event.author.name,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.channel.id,
                        name=event.channel.name,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event.created_at.timestamp(),
                source_platform_object=event,
            )


class DiscordAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: discord.Client = pydantic.Field(exclude=True)

    message_converter: DiscordMessageConverter = DiscordMessageConverter()
    event_converter: DiscordEventConverter = DiscordEventConverter()

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    voice_manager: VoiceConnectionManager | None = pydantic.Field(exclude=True, default=None)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        bot_account_id = config['client_id']

        listeners = {}

        # 初始化语音连接管理器
        # self.voice_manager: VoiceConnectionManager = None

        adapter_self = self

        class MyClient(discord.Client):
            async def on_message(self: discord.Client, message: discord.Message):
                if message.author.id == self.user.id or message.author.bot:
                    return

                lb_event = await adapter_self.event_converter.target2yiri(message)
                await adapter_self.listeners[type(lb_event)](lb_event, adapter_self)

        intents = discord.Intents.default()
        intents.message_content = True

        args = {}

        if os.getenv('http_proxy'):
            args['proxy'] = os.getenv('http_proxy')

        bot = MyClient(intents=intents, **args)

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=bot_account_id,
            listeners=listeners,
            bot=bot,
            voice_manager=None,
            **kwargs,
        )

    # Voice functionality methods
    async def join_voice_channel(self, guild_id: int, channel_id: int, user_id: int = None) -> discord.VoiceClient:
        """
        加入语音频道

        为指定服务器的语音频道建立连接，支持用户权限验证和连接复用。

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Args:
            guild_id (int): Discord 服务器ID
            channel_id (int): 语音频道ID
            user_id (int, optional): 请求用户ID，用于权限验证

        Returns:
            discord.VoiceClient: 语音客户端实例

        Raises:
            VoicePermissionError: 权限不足
            VoiceNetworkError: 网络连接失败
            VoiceConnectionError: 其他连接错误
        """
        if not self.voice_manager:
            raise VoiceConnectionError('语音管理器未初始化', 'MANAGER_NOT_READY')

        return await self.voice_manager.join_voice_channel(guild_id, channel_id, user_id)

    async def leave_voice_channel(self, guild_id: int) -> bool:
        """
        离开语音频道

        断开指定服务器的语音连接，清理相关资源。

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Args:
            guild_id (int): Discord 服务器ID

        Returns:
            bool: 是否成功断开连接
        """
        if not self.voice_manager:
            return False

        return await self.voice_manager.leave_voice_channel(guild_id)

    async def get_voice_client(self, guild_id: int) -> typing.Optional[discord.VoiceClient]:
        """
        获取语音客户端

        返回指定服务器的语音客户端实例，用于音频播放控制。

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Args:
            guild_id (int): Discord 服务器ID

        Returns:
            Optional[discord.VoiceClient]: 语音客户端实例或 None
        """
        if not self.voice_manager:
            return None

        return await self.voice_manager.get_voice_client(guild_id)

    async def is_connected_to_voice(self, guild_id: int) -> bool:
        """
        检查语音连接状态

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Args:
            guild_id (int): Discord 服务器ID

        Returns:
            bool: 是否已连接到语音频道
        """
        if not self.voice_manager:
            return False

        return await self.voice_manager.is_connected_to_voice(guild_id)

    async def get_voice_connection_status(self, guild_id: int) -> typing.Optional[dict]:
        """
        获取语音连接详细状态

        返回包含连接时间、延迟、用户数等详细信息的状态字典。

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Args:
            guild_id (int): Discord 服务器ID

        Returns:
            Optional[dict]: 连接状态信息或 None
        """
        if not self.voice_manager:
            return None

        return await self.voice_manager.get_connection_status(guild_id)

    async def list_active_voice_connections(self) -> typing.List[dict]:
        """
        列出所有活跃的语音连接

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Returns:
            List[dict]: 活跃语音连接列表
        """
        if not self.voice_manager:
            return []

        return await self.voice_manager.list_active_connections()

    async def get_voice_channel_info(self, guild_id: int, channel_id: int) -> typing.Optional[dict]:
        """
        获取语音频道详细信息

        包括频道名称、用户列表、权限信息等。

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04

        Args:
            guild_id (int): Discord 服务器ID
            channel_id (int): 语音频道ID

        Returns:
            Optional[dict]: 频道信息字典或 None
        """
        if not self.voice_manager:
            return None

        return await self.voice_manager.get_voice_channel_info(guild_id, channel_id)

    async def cleanup_voice_connections(self):
        """
        清理无效的语音连接

        手动触发语音连接清理，移除已断开或无效的连接。

        @author: @ydzat
        @version: 1.0
        @since: 2025-07-04
        """
        if self.voice_manager:
            await self.voice_manager.cleanup_inactive_connections()

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        msg_to_send, image_files = await self.message_converter.yiri2target(message)

        try:
            # 获取频道对象
            channel = self.bot.get_channel(int(target_id))
            if channel is None:
                # 如果本地缓存中没有，尝试从API获取
                channel = await self.bot.fetch_channel(int(target_id))

            args = {
                'content': msg_to_send,
            }

            if len(image_files) > 0:
                args['files'] = image_files

            await channel.send(**args)

        except Exception as e:
            await self.logger.error(f'Discord send_message failed: {e}')
            raise e

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        msg_to_send, image_files = await self.message_converter.yiri2target(message)
        assert isinstance(message_source.source_platform_object, discord.Message)

        args = {
            'content': msg_to_send,
        }

        if len(image_files) > 0:
            args['files'] = image_files

        if quote_origin:
            args['reference'] = message_source.source_platform_object

        has_at = False

        for component in message.root:
            if isinstance(component, platform_message.At):
                has_at = True
                break

        if has_at:
            args['mention_author'] = True

        await message_source.source_platform_object.channel.send(**args)

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
        """
        启动 Discord 适配器

        初始化语音管理器并启动 Discord 客户端连接。

        @author: @ydzat (修改)
        """
        async with self.bot:
            # 初始化语音管理器
            self.voice_manager = VoiceConnectionManager(self.bot, self.logger)
            await self.voice_manager.start_monitoring()

            await self.logger.info('Discord 适配器语音功能已启用')
            await self.bot.start(self.config['token'], reconnect=True)

    async def kill(self) -> bool:
        """
        关闭 Discord 适配器

        清理语音连接并关闭 Discord 客户端。

        @author: @ydzat (修改)
        """
        if self.voice_manager:
            await self.voice_manager.disconnect_all()

        await self.bot.close()
        return True
