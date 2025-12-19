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
from .websocket_manager import ws_connection_manager, WebSocketConnection

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

    def __init__(self, id: str):
        self.id = id
        self.message_lists = {}

    def get_message_list(self, pipeline_uuid: str) -> list[WebSocketMessage]:
        if pipeline_uuid not in self.message_lists:
            self.message_lists[pipeline_uuid] = []
        return self.message_lists[pipeline_uuid]


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

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> dict:
        """发送消息 - 这里用于主动推送消息到前端"""
        message_data = {
            'type': 'bot_message',
            'target_type': target_type,
            'target_id': target_id,
            'content': str(message),
            'message_chain': [component.__dict__ for component in message],
            'timestamp': datetime.now().isoformat(),
        }

        # 推送到所有相关连接
        await self.outbound_message_queue.put(message_data)

        return message_data

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

        # 从message_source获取pipeline_uuid和connection_id
        pipeline_uuid = self.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid
        session_type = 'group' if isinstance(message_source, platform_events.GroupMessage) else 'person'

        # 生成新的消息ID
        msg_id = len(session.get_message_list(pipeline_uuid)) + 1

        message_data = WebSocketMessage(
            id=msg_id,
            role='assistant',
            content=str(message),
            message_chain=[component.__dict__ for component in message],
            timestamp=datetime.now().isoformat(),
            is_final=True,
        )

        # 保存到历史记录
        session.get_message_list(pipeline_uuid).append(message_data)

        # 直接广播到所有该pipeline的连接，包含session_type信息
        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'response',
                'session_type': session_type,
                'data': message_data.model_dump(),
            },
            session_type=session_type,
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

        pipeline_uuid = self.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid
        session_type = 'group' if isinstance(message_source, platform_events.GroupMessage) else 'person'
        message_list = session.get_message_list(pipeline_uuid)

        # 检查是否是新的流式消息（通过bot_message对象判断）
        # 如果列表为空，或者最后一条消息已经is_final=True，则创建新消息
        if not message_list or message_list[-1].is_final:
            # 创建新消息
            msg_id = len(message_list) + 1
            message_data = WebSocketMessage(
                id=msg_id,
                role='assistant',
                content=str(message),
                message_chain=[component.__dict__ for component in message],
                timestamp=datetime.now().isoformat(),
                is_final=is_final and bot_message.tool_calls is None,
            )

            # 只有在is_final时才保存到历史记录
            if is_final and bot_message.tool_calls is None:
                message_list.append(message_data)
        else:
            # 更新最后一条消息
            msg_id = message_list[-1].id
            message_data = WebSocketMessage(
                id=msg_id,
                role='assistant',
                content=str(message),
                message_chain=[component.__dict__ for component in message],
                timestamp=message_list[-1].timestamp,  # 保持原始时间戳
                is_final=is_final and bot_message.tool_calls is None,
            )

            # 如果是final，更新历史记录中的最后一条
            if is_final and bot_message.tool_calls is None:
                message_list[-1] = message_data

        # 直接广播到所有该pipeline的连接，包含session_type信息
        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'response',
                'session_type': session_type,
                'data': message_data.model_dump(),
            },
            session_type=session_type,
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
        处理消息链中的图片组件，将path转换为base64

        Args:
            message_chain_obj: 消息链对象列表
        """
        import base64

        storage_mgr = self.ap.storage_mgr

        for component in message_chain_obj:
            if component.get('type') == 'Image' and component.get('path'):
                try:
                    # 从storage读取文件
                    file_content = await storage_mgr.storage_provider.load(component['path'])

                    # 转换为base64
                    base64_str = base64.b64encode(file_content).decode('utf-8')

                    # 添加data URI前缀（根据文件扩展名判断MIME类型）
                    file_key = component['path']
                    if file_key.lower().endswith(('.jpg', '.jpeg')):
                        mime_type = 'image/jpeg'
                    elif file_key.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif file_key.lower().endswith('.gif'):
                        mime_type = 'image/gif'
                    elif file_key.lower().endswith('.webp'):
                        mime_type = 'image/webp'
                    else:
                        mime_type = 'image/png'  # 默认

                    component['base64'] = f'data:{mime_type};base64,{base64_str}'
                    await storage_mgr.storage_provider.delete(component['path'])
                    component['path'] = ''
                    # 保留path字段用于后端处理，前端使用base64显示
                except Exception as e:
                    await self.logger.error(f'加载图片文件失败 {component["path"]}: {e}')

    async def handle_websocket_message(
        self,
        connection: WebSocketConnection,
        message_data: dict,
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
        """
        pipeline_uuid = connection.pipeline_uuid
        session_type = connection.session_type

        # 获取stream参数，默认为True
        self.stream_enabled = message_data.get('stream', True)

        # 选择会话
        use_session = self.websocket_group_session if session_type == 'group' else self.websocket_person_session

        # 解析消息链
        message_chain_obj = message_data.get('message', [])

        # 处理图片组件：将path转换为base64
        await self._process_image_components(message_chain_obj)

        message_chain = platform_message.MessageChain.model_validate(message_chain_obj)

        # 生成消息ID
        message_id = len(use_session.get_message_list(pipeline_uuid)) + 1

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
        use_session.get_message_list(pipeline_uuid).append(user_message)

        # 广播用户消息到所有连接（包括发送者），包含session_type信息
        await ws_connection_manager.broadcast_to_pipeline(
            pipeline_uuid,
            {
                'type': 'user_message',
                'session_type': session_type,
                'data': user_message.model_dump(),
            },
            session_type=session_type,
        )

        # 添加消息源
        message_chain.insert(0, platform_message.Source(id=message_id, time=datetime.now().timestamp()))

        # 创建事件
        if session_type == 'person':
            sender = platform_entities.Friend(
                id=f'websocket_{connection.connection_id}', nickname='User', remark='User'
            )
            event = platform_events.FriendMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )
        else:
            group = platform_entities.Group(
                id='websocketgroup', name='Group', permission=platform_entities.Permission.Member
            )
            sender = platform_entities.GroupMember(
                id=f'websocket_{connection.connection_id}',
                member_name='User',
                group=group,
                permission=platform_entities.Permission.Member,
            )
            event = platform_events.GroupMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )

        # 设置流水线UUID
        self.ap.platform_mgr.websocket_proxy_bot.bot_entity.use_pipeline_uuid = pipeline_uuid

        # 异步触发事件处理（不等待结果）
        if event.__class__ in self.listeners:
            asyncio.create_task(self.listeners[event.__class__](event, self))

    def get_websocket_messages(self, pipeline_uuid: str, session_type: str) -> list[dict]:
        """获取消息历史"""
        if session_type == 'person':
            return [message.model_dump() for message in self.websocket_person_session.get_message_list(pipeline_uuid)]
        else:
            return [message.model_dump() for message in self.websocket_group_session.get_message_list(pipeline_uuid)]

    def reset_session(self, pipeline_uuid: str, session_type: str):
        """重置会话"""
        if session_type == 'person':
            if pipeline_uuid in self.websocket_person_session.message_lists:
                self.websocket_person_session.message_lists[pipeline_uuid] = []
        else:
            if pipeline_uuid in self.websocket_group_session.message_lists:
                self.websocket_group_session.message_lists[pipeline_uuid] = []
