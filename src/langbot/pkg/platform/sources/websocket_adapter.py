"""WebSocket适配器 - 支持双向通信的IM系统"""

import asyncio
import logging
import typing
from datetime import datetime

import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from ...core import app
from .websocket_manager import WebSocketConnection, is_valid_session_id, ws_connection_manager

logger = logging.getLogger(__name__)


class WebSocketMessage(pydantic.BaseModel):
    """WebSocket消息格式"""

    id: int
    role: str  # 'user' or 'assistant'
    content: str
    message_chain: list[dict]
    timestamp: str
    is_final: bool = False
    connection_id: str = ''
    """发送者连接ID"""


class WebSocketSession:
    """WebSocket会话 - 管理单个会话的消息历史"""

    id: str
    message_lists: dict[str, list[WebSocketMessage]] = {}
    """消息列表 {pipeline_uuid: [messages]}"""
    stream_message_indexes: dict[str, dict[str, int]] = {}
    """流式消息索引 {pipeline_uuid: {resp_message_id: message_index}}"""

    def __init__(self, id: str):
        self.id = id
        self.message_lists = {}
        self.stream_message_indexes = {}

    def get_message_list(self, pipeline_uuid: str) -> list[WebSocketMessage]:
        if pipeline_uuid not in self.message_lists:
            self.message_lists[pipeline_uuid] = []
        return self.message_lists[pipeline_uuid]

    def get_stream_message_indexes(self, pipeline_uuid: str) -> dict[str, int]:
        if pipeline_uuid not in self.stream_message_indexes:
            self.stream_message_indexes[pipeline_uuid] = {}
        return self.stream_message_indexes[pipeline_uuid]


class WebSocketAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """WebSocket适配器 - 支持双向实时通信"""

    websocket_person_session: WebSocketSession = pydantic.Field(exclude=True, default_factory=WebSocketSession)
    websocket_group_session: WebSocketSession = pydantic.Field(exclude=True, default_factory=WebSocketSession)

    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = pydantic.Field(default_factory=dict, exclude=True)

    ap: app.Application = pydantic.Field(exclude=True)

    # 主动推送消息的队列
    outbound_message_queue: asyncio.Queue = pydantic.Field(default_factory=asyncio.Queue, exclude=True)
    """后端主动推送消息的队列"""

    # 流式输出开关
    stream_enabled: bool = pydantic.Field(default=True, exclude=True)
    """是否启用流式输出"""

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        super().__init__(
            config=config,
            logger=logger,
            **kwargs,
        )

        self.websocket_person_session = WebSocketSession(id='websocketperson')
        self.websocket_group_session = WebSocketSession(id='websocketgroup')

        self.bot_account_id = 'websocketbot'
        self.outbound_message_queue = asyncio.Queue()
        self.stream_enabled = True

    @staticmethod
    def _conversation_key(pipeline_uuid: str, session_id: str | None = None) -> str:
        """Return the history key for a pipeline/client conversation."""
        return f'{pipeline_uuid}:{session_id}' if session_id else pipeline_uuid

    @staticmethod
    def _parse_embed_target(target_id: str) -> tuple[str, str] | None:
        """Extract pipeline and session identifiers from a stable embed launcher."""
        target_value = str(target_id)
        for prefix in ('websocket_', 'websocketgroup_'):
            if target_value.startswith(prefix):
                target = target_value[len(prefix) :]
                break
        else:
            return None
        if ':' not in target:
            return None
        pipeline_uuid, session_id = target.rsplit(':', 1)
        if not pipeline_uuid or not is_valid_session_id(session_id):
            return None
        return pipeline_uuid, session_id

    @classmethod
    async def _get_connection_from_target(cls, target_id: str):
        """Resolve a person or group WebSocket launcher to its connection."""
        target_value = str(target_id)
        for prefix in ('websocket_', 'websocketgroup_'):
            if target_value.startswith(prefix):
                target = target_value[len(prefix) :]
                break
        else:
            return None
        connection = await ws_connection_manager.get_connection(target)
        if connection is not None:
            return connection
        embed_target = cls._parse_embed_target(target_id)
        if embed_target is not None:
            pipeline_uuid, session_id = embed_target
            return await ws_connection_manager.get_connection_by_session_id(session_id, pipeline_uuid)
        return await ws_connection_manager.get_connection_by_session_id(target)

    async def _get_message_context(self, message_source) -> tuple[str, str | None]:
        """Resolve the originating pipeline and browser session for a reply."""
        sender = getattr(message_source, 'sender', None)
        sender_id = getattr(sender, 'id', '')
        connection = await self._get_connection_from_target(sender_id)
        if connection is not None:
            return connection.pipeline_uuid, connection.session_id
        embed_target = self._parse_embed_target(sender_id)
        if embed_target is not None:
            return embed_target
        return typing.cast(str, self.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid), None

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> dict:
        """发送消息 - 这里用于主动推送消息到前端

        对于 WebSocket 适配器，我们需要将消息广播到正确的 pipeline 连接。
        target_id 可能是 launcher_id（如 websocket_xxx）或 pipeline_uuid。
        我们需要尝试两种方式来确保消息能够送达。
        """
        connection = await self._get_connection_from_target(target_id)
        if connection is not None:
            pipeline_uuid = connection.pipeline_uuid
            session_id = connection.session_id
        else:
            embed_target = self._parse_embed_target(target_id)
            if embed_target is not None:
                pipeline_uuid, session_id = embed_target
            else:
                pipeline_uuid = typing.cast(
                    str,
                    self.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid,
                )
                session_id = None
        session_type = 'group' if target_type == 'group' else 'person'
        conversation_key = self._conversation_key(pipeline_uuid, session_id)

        session = self.websocket_group_session if session_type == 'group' else self.websocket_person_session

        msg_id = len(session.get_message_list(conversation_key)) + 1

        message_data = WebSocketMessage(
            id=msg_id,
            role='assistant',
            content=str(message),
            message_chain=[component.__dict__ for component in message],
            timestamp=datetime.now().isoformat(),
            is_final=True,
        )

        session.get_message_list(conversation_key).append(message_data)

        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'response',
                'session_type': session_type,
                'data': message_data.model_dump(),
            },
            session_type=session_type,
            session_id=session_id,
        )

        return message_data.model_dump()

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        """回复消息 - 非流式"""
        # 获取会话和pipeline信息
        session = (
            self.websocket_group_session
            if isinstance(message_source, platform_events.GroupMessage)
            else self.websocket_person_session
        )

        pipeline_uuid, session_id = await self._get_message_context(message_source)
        session_type = 'group' if isinstance(message_source, platform_events.GroupMessage) else 'person'
        conversation_key = self._conversation_key(pipeline_uuid, session_id)

        msg_id = len(session.get_message_list(conversation_key)) + 1

        message_data = WebSocketMessage(
            id=msg_id,
            role='assistant',
            content=str(message),
            message_chain=[component.__dict__ for component in message],
            timestamp=datetime.now().isoformat(),
            is_final=True,
        )

        session.get_message_list(conversation_key).append(message_data)

        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'response',
                'session_type': session_type,
                'data': message_data.model_dump(),
            },
            session_type=session_type,
            session_id=session_id,
        )

        return message_data.model_dump()

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        """回复消息块 - 流式"""
        # 获取会话和pipeline信息
        session = (
            self.websocket_group_session
            if isinstance(message_source, platform_events.GroupMessage)
            else self.websocket_person_session
        )

        pipeline_uuid, session_id = await self._get_message_context(message_source)
        session_type = 'group' if isinstance(message_source, platform_events.GroupMessage) else 'person'
        conversation_key = self._conversation_key(pipeline_uuid, session_id)
        message_list = session.get_message_list(conversation_key)
        stream_message_indexes = session.get_stream_message_indexes(conversation_key)

        # Streaming messages in LangBot have a stable resp_message_id during the same assistant reply.
        # Use it as the primary key to avoid overwriting an old card from a previous reply.
        resp_message_id = str(getattr(bot_message, 'resp_message_id', '') or '')
        existing_index = stream_message_indexes.get(resp_message_id) if resp_message_id else None

        message_is_final = is_final and bot_message.tool_calls is None

        if existing_index is None or existing_index >= len(message_list):
            # 创建新消息
            msg_id = len(message_list) + 1
            message_data = WebSocketMessage(
                id=msg_id,
                role='assistant',
                content=str(message),
                message_chain=[component.__dict__ for component in message],
                timestamp=datetime.now().isoformat(),
                is_final=message_is_final,
            )

            # 立即添加到历史记录（即使is_final=False），以便后续块可以更新它
            message_list.append(message_data)
            if resp_message_id:
                stream_message_indexes[resp_message_id] = len(message_list) - 1
        else:
            # 更新同一条流式消息
            old_message = message_list[existing_index]
            msg_id = old_message.id
            message_data = WebSocketMessage(
                id=msg_id,
                role='assistant',
                content=str(message),
                message_chain=[component.__dict__ for component in message],
                timestamp=old_message.timestamp,  # 保持原始时间戳
                is_final=message_is_final,
            )

            # 更新历史记录中的对应消息
            message_list[existing_index] = message_data

        if message_is_final and resp_message_id:
            stream_message_indexes.pop(resp_message_id, None)

        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'response',
                'session_type': session_type,
                'data': message_data.model_dump(),
            },
            session_type=session_type,
            session_id=session_id,
        )

        return message_data.model_dump()

    async def is_stream_output_supported(self) -> bool:
        """根据stream_enabled标志返回是否支持流式输出"""
        return self.stream_enabled

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        """注册事件监听器"""
        self.listeners[event_type] = func

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        """取消注册事件监听器"""
        del self.listeners[event_type]

    async def is_muted(self, group_id: int) -> bool:
        return False

    async def run_async(self):
        """运行适配器"""

        try:
            while True:
                # 处理主动推送消息
                if not self.outbound_message_queue.empty():
                    try:
                        message = await asyncio.wait_for(self.outbound_message_queue.get(), timeout=0.1)
                        # 广播到所有相关连接
                        target_id = message.get('target_id', '')
                        await ws_connection_manager.broadcast_to_pipeline(target_id, message)
                    except asyncio.TimeoutError:
                        pass

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise

    async def kill(self):
        """停止适配器"""
        pass

    async def _process_image_components(self, message_chain_obj: list):
        """
        处理消息链中的图片、语音和文件组件，将 path 转换为 base64

        Image / Voice / File components uploaded from the web client carry a
        storage key in ``path``. Resolve it to a base64 data URI so downstream
        stages (multimodal LLM input and the Box sandbox inbox) have a usable
        payload, then drop the now-consumed storage object.

        Args:
            message_chain_obj: 消息链对象列表
        """
        import base64
        import mimetypes

        storage_mgr = self.ap.storage_mgr

        for component in message_chain_obj:
            comp_type = component.get('type', '')
            comp_path = component.get('path', '')

            if not comp_path or comp_type not in ('Image', 'Voice', 'File'):
                continue

            try:
                file_content = await storage_mgr.storage_provider.load(comp_path)
                base64_str = base64.b64encode(file_content).decode('utf-8')

                lowered = comp_path.lower()
                if comp_type == 'Image':
                    if lowered.endswith(('.jpg', '.jpeg')):
                        mime_type = 'image/jpeg'
                    elif lowered.endswith('.gif'):
                        mime_type = 'image/gif'
                    elif lowered.endswith('.webp'):
                        mime_type = 'image/webp'
                    else:
                        mime_type = 'image/png'
                elif comp_type == 'Voice':
                    mime_type = mimetypes.guess_type(comp_path)[0] or 'audio/wav'
                else:  # File
                    mime_type = mimetypes.guess_type(comp_path)[0] or 'application/octet-stream'

                component['base64'] = f'data:{mime_type};base64,{base64_str}'
                await storage_mgr.storage_provider.delete(comp_path)
                component['path'] = ''
            except Exception as e:
                await self.logger.error(f'Failed to load {comp_type} file {comp_path}: {e}')

    async def handle_websocket_message(
        self,
        connection: WebSocketConnection,
        message_data: dict,
        owner_bot=None,
    ):
        """
        处理从WebSocket接收的消息

        这个方法只负责接收消息、保存到历史记录、并触发事件处理
        不等待任何响应，响应消息会通过reply_message/reply_message_chunk直接发送

        Args:
            connection: WebSocket连接对象
            message_data: 消息数据，包含:
                - message: 消息链
                - stream: 是否启用流式输出 (可选，默认True)
            owner_bot: Optional RuntimeBot that owns this pipeline (e.g. a web_page_bot).
                       When provided, its identity is used for logging and session tracking.
        """
        pipeline_uuid = connection.pipeline_uuid
        session_type = connection.session_type
        conversation_key = self._conversation_key(pipeline_uuid, connection.session_id)

        self.stream_enabled = message_data.get('stream', True)

        use_session = self.websocket_group_session if session_type == 'group' else self.websocket_person_session

        message_chain_obj = message_data.get('message', [])

        await self._process_image_components(message_chain_obj)

        message_chain = platform_message.MessageChain.model_validate(message_chain_obj)

        message_id = len(use_session.get_message_list(conversation_key)) + 1

        # 保存用户消息
        user_message = WebSocketMessage(
            id=message_id,
            role='user',
            content=str(message_chain),
            message_chain=message_chain_obj,
            timestamp=datetime.now().isoformat(),
            connection_id=connection.connection_id,
            is_final=True,  # 用户消息始终是完整的，非流式
        )
        use_session.get_message_list(conversation_key).append(user_message)

        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'user_message',
                'session_type': session_type,
                'data': user_message.model_dump(),
            },
            session_type=session_type,
            session_id=connection.session_id,
        )

        # 添加消息源
        message_chain.insert(0, platform_message.Source(id=message_id, time=datetime.now().timestamp()))

        # 创建事件
        launcher_id = f'{pipeline_uuid}:{connection.session_id}' if connection.session_id else connection.connection_id
        if session_type == 'person':
            sender = platform_entities.Friend(id=f'websocket_{launcher_id}', nickname='User', remark='User')
            event = platform_events.FriendMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )
        else:
            group = platform_entities.Group(
                id=f'websocketgroup_{launcher_id}' if connection.session_id else 'websocketgroup',
                name='Group',
                permission=platform_entities.Permission.Member,
            )
            sender = platform_entities.GroupMember(
                id=f'websocket_{launcher_id}',
                member_name='User',
                group=group,
                permission=platform_entities.Permission.Member,
            )
            event = platform_events.GroupMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )

        object.__setattr__(event, '_langbot_pipeline_uuid', pipeline_uuid)

        # 异步触发事件处理
        # Use owner_bot's listeners if available, otherwise fall back to proxy bot
        listeners = (
            owner_bot.adapter.listeners
            if (owner_bot and hasattr(owner_bot.adapter, 'listeners') and owner_bot.adapter.listeners)
            else self.listeners
        )
        # Pass owner_bot's adapter so that downstream logging / dashboard
        # attributes the message to the correct bot adapter name.
        # Wire the ws adapter into the owner so replies are actually delivered.
        if owner_bot and hasattr(owner_bot.adapter, 'set_ws_adapter'):
            owner_bot.adapter.set_ws_adapter(self)
        callback_adapter = owner_bot.adapter if (owner_bot and hasattr(owner_bot, 'adapter')) else self
        if event.__class__ in listeners:
            asyncio.create_task(listeners[event.__class__](event, callback_adapter))

    def get_websocket_messages(
        self,
        pipeline_uuid: str,
        session_type: str,
        session_id: str | None = None,
    ) -> list[dict]:
        """Return history for one pipeline/client conversation."""
        conversation_key = self._conversation_key(pipeline_uuid, session_id)
        session = self.websocket_person_session if session_type == 'person' else self.websocket_group_session
        return [message.model_dump() for message in session.message_lists.get(conversation_key, [])]

    def reset_session(
        self,
        pipeline_uuid: str,
        session_type: str,
        session_id: str | None = None,
    ):
        """Reset one pipeline/client conversation."""
        conversation_key = self._conversation_key(pipeline_uuid, session_id)
        session = self.websocket_person_session if session_type == 'person' else self.websocket_group_session
        if conversation_key in session.message_lists:
            session.message_lists[conversation_key] = []
        if conversation_key in session.stream_message_indexes:
            session.stream_message_indexes[conversation_key] = {}

        if session_id:
            launcher_id = (
                f'websocketgroup_{pipeline_uuid}:{session_id}'
                if session_type == 'group'
                else f'websocket_{pipeline_uuid}:{session_id}'
            )
            self.ap.sess_mgr.session_list = [
                candidate_session
                for candidate_session in self.ap.sess_mgr.session_list
                if not (
                    str(
                        candidate_session.launcher_type.value
                        if hasattr(candidate_session.launcher_type, 'value')
                        else candidate_session.launcher_type
                    )
                    == session_type
                    and str(candidate_session.launcher_id) == launcher_id
                )
            ]
