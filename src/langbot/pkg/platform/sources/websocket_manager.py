"""WebSocket连接管理器 - 管理多个并发WebSocket连接"""

import asyncio
import logging
import typing
import uuid
from datetime import datetime

import pydantic

logger = logging.getLogger(__name__)


class WebSocketConnection(pydantic.BaseModel):
    """单个WebSocket连接"""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    connection_id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
    """连接唯一ID"""

    pipeline_uuid: str
    """关联的流水线UUID"""

    session_type: str  # 'person' or 'group'
    """会话类型"""

    websocket: typing.Any = pydantic.Field(exclude=True)
    """WebSocket连接对象 (quart.websocket)"""

    created_at: datetime = pydantic.Field(default_factory=datetime.now)
    """连接创建时间"""

    last_active: datetime = pydantic.Field(default_factory=datetime.now)
    """最后活跃时间"""

    send_queue: asyncio.Queue = pydantic.Field(default_factory=asyncio.Queue, exclude=True)
    """发送消息队列"""

    is_active: bool = True
    """连接是否活跃"""

    metadata: dict = pydantic.Field(default_factory=dict)
    """连接元数据（可存储额外信息）"""


class WebSocketConnectionManager:
    """WebSocket连接管理器 - 支持多连接并发"""

    def __init__(self):
        self.connections: dict[str, WebSocketConnection] = {}
        """所有活跃连接 {connection_id: connection}"""

        self.pipeline_connections: dict[str, set[str]] = {}
        """流水线到连接的映射 {pipeline_uuid: {connection_id, ...}}"""

        self.session_connections: dict[str, set[str]] = {}
        """会话类型到连接的映射 {session_type: {connection_id, ...}}"""

        self._lock = asyncio.Lock()
        """线程锁，保护并发访问"""

    async def add_connection(
        self,
        websocket: typing.Any,
        pipeline_uuid: str,
        session_type: str,
        metadata: dict = None,
    ) -> WebSocketConnection:
        """添加新的WebSocket连接"""
        async with self._lock:
            connection = WebSocketConnection(
                pipeline_uuid=pipeline_uuid,
                session_type=session_type,
                websocket=websocket,
                metadata=metadata or {},
            )

            self.connections[connection.connection_id] = connection

            # 更新流水线映射
            if pipeline_uuid not in self.pipeline_connections:
                self.pipeline_connections[pipeline_uuid] = set()
            self.pipeline_connections[pipeline_uuid].add(connection.connection_id)

            # 更新会话类型映射
            if session_type not in self.session_connections:
                self.session_connections[session_type] = set()
            self.session_connections[session_type].add(connection.connection_id)

            logger.debug(
                f'WebSocket connection established: {connection.connection_id} '
                f'(pipeline={pipeline_uuid}, session_type={session_type})'
            )

            return connection

    async def remove_connection(self, connection_id: str):
        """移除WebSocket连接"""
        async with self._lock:
            if connection_id not in self.connections:
                return

            connection = self.connections[connection_id]
            connection.is_active = False

            # 从流水线映射中移除
            if connection.pipeline_uuid in self.pipeline_connections:
                self.pipeline_connections[connection.pipeline_uuid].discard(connection_id)
                if not self.pipeline_connections[connection.pipeline_uuid]:
                    del self.pipeline_connections[connection.pipeline_uuid]

            # 从会话类型映射中移除
            if connection.session_type in self.session_connections:
                self.session_connections[connection.session_type].discard(connection_id)
                if not self.session_connections[connection.session_type]:
                    del self.session_connections[connection.session_type]

            del self.connections[connection_id]

            logger.debug(f'WebSocket connection disconnected: {connection_id}')

    async def get_connection(self, connection_id: str) -> typing.Optional[WebSocketConnection]:
        """获取指定连接"""
        return self.connections.get(connection_id)

    async def get_connections_by_pipeline(self, pipeline_uuid: str) -> list[WebSocketConnection]:
        """获取指定流水线的所有连接"""
        connection_ids = self.pipeline_connections.get(pipeline_uuid, set())
        return [self.connections[cid] for cid in connection_ids if cid in self.connections]

    async def get_connections_by_session_type(self, session_type: str) -> list[WebSocketConnection]:
        """获取指定会话类型的所有连接"""
        connection_ids = self.session_connections.get(session_type, set())
        return [self.connections[cid] for cid in connection_ids if cid in self.connections]

    async def broadcast_to_pipeline(self, pipeline_uuid: str, message: dict, session_type: str = None):
        """向指定流水线的所有连接广播消息

        Args:
            pipeline_uuid: 流水线UUID
            message: 要广播的消息
            session_type: 可选的会话类型过滤器，如果提供则只向匹配的session_type连接广播
        """
        connections = await self.get_connections_by_pipeline(pipeline_uuid)

        # 如果指定了session_type，只向匹配的连接广播
        if session_type is not None:
            connections = [conn for conn in connections if conn.session_type == session_type]

        tasks = []
        for conn in connections:
            tasks.append(self.send_to_connection(conn.connection_id, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to_connection(self, connection_id: str, message: dict):
        """向指定连接发送消息"""
        connection = await self.get_connection(connection_id)
        if not connection or not connection.is_active:
            logger.warning(f'Attempt to send message to invalid connection: {connection_id}')
            return

        try:
            await connection.send_queue.put(message)
            connection.last_active = datetime.now()
        except Exception as e:
            logger.error(f'Failed to send message to connection {connection_id}: {e}')
            await self.remove_connection(connection_id)

    async def update_activity(self, connection_id: str):
        """更新连接活跃时间"""
        connection = await self.get_connection(connection_id)
        if connection:
            connection.last_active = datetime.now()

    def get_stats(self) -> dict:
        """获取连接统计信息"""
        return {
            'total_connections': len(self.connections),
            'pipelines': len(self.pipeline_connections),
            'connections_by_pipeline': {k: len(v) for k, v in self.pipeline_connections.items()},
            'connections_by_session_type': {k: len(v) for k, v in self.session_connections.items()},
        }


# 全局连接管理器实例
ws_connection_manager = WebSocketConnectionManager()
