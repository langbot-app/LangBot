"""WebSocket 连接池管理

用于管理流水线调试的 WebSocket 连接，支持会话隔离和消息广播。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import quart

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """单个 WebSocket 连接"""

    connection_id: str
    websocket: quart.websocket.WebSocket
    pipeline_uuid: str
    session_type: str  # 'person' 或 'group'
    created_at: datetime
    last_ping: datetime

    @property
    def session_key(self) -> str:
        """会话唯一标识: pipeline_uuid:session_type"""
        return f"{self.pipeline_uuid}:{self.session_type}"

    async def send(self, event_type: str, data: dict):
        """发送事件到客户端

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        try:
            await self.websocket.send_json({"type": event_type, "data": data})
        except Exception as e:
            logger.error(f"Failed to send message to {self.connection_id}: {e}")
            raise


class WebSocketConnectionPool:
    """WebSocket 连接池 - 按会话隔离

    连接池结构:
        connections[session_key][connection_id] = WebSocketConnection
        其中 session_key = f"{pipeline_uuid}:{session_type}"

    这样可以确保:
        - person 和 group 会话完全隔离
        - 不同 pipeline 的会话隔离
        - 同一会话的多个连接可以同步接收消息（多标签页）
    """

    def __init__(self):
        self.connections: dict[str, dict[str, WebSocketConnection]] = {}
        self._lock = asyncio.Lock()

    def add_connection(self, conn: WebSocketConnection):
        """添加连接到指定会话

        Args:
            conn: WebSocket 连接对象
        """
        session_key = conn.session_key

        if session_key not in self.connections:
            self.connections[session_key] = {}

        self.connections[session_key][conn.connection_id] = conn

        logger.info(
            f"WebSocket connection added: {conn.connection_id} "
            f"to session {session_key} "
            f"(total: {len(self.connections[session_key])} connections)"
        )

    async def remove_connection(self, connection_id: str, session_key: str):
        """从指定会话移除连接

        Args:
            connection_id: 连接 ID
            session_key: 会话标识
        """
        async with self._lock:
            if session_key in self.connections:
                conn = self.connections[session_key].pop(connection_id, None)

                # 如果该会话没有连接了，清理会话
                if not self.connections[session_key]:
                    del self.connections[session_key]

                if conn:
                    logger.info(
                        f"WebSocket connection removed: {connection_id} "
                        f"from session {session_key} "
                        f"(remaining: {len(self.connections.get(session_key, {}))} connections)"
                    )

    def get_connection(self, connection_id: str, session_key: str) -> Optional[WebSocketConnection]:
        """获取指定连接

        Args:
            connection_id: 连接 ID
            session_key: 会话标识

        Returns:
            WebSocketConnection 或 None
        """
        return self.connections.get(session_key, {}).get(connection_id)

    def get_connections_by_session(self, pipeline_uuid: str, session_type: str) -> list[WebSocketConnection]:
        """获取指定会话的所有连接

        Args:
            pipeline_uuid: 流水线 UUID
            session_type: 会话类型 ('person' 或 'group')

        Returns:
            连接列表
        """
        session_key = f"{pipeline_uuid}:{session_type}"
        return list(self.connections.get(session_key, {}).values())

    async def broadcast_to_session(self, pipeline_uuid: str, session_type: str, event_type: str, data: dict):
        """广播消息到指定会话的所有连接

        Args:
            pipeline_uuid: 流水线 UUID
            session_type: 会话类型 ('person' 或 'group')
            event_type: 事件类型
            data: 事件数据
        """
        connections = self.get_connections_by_session(pipeline_uuid, session_type)

        if not connections:
            logger.debug(f"No connections for session {pipeline_uuid}:{session_type}, skipping broadcast")
            return

        logger.debug(
            f"Broadcasting {event_type} to session {pipeline_uuid}:{session_type}, " f"{len(connections)} connections"
        )

        # 并发发送到所有连接，忽略失败的连接
        results = await asyncio.gather(*[conn.send(event_type, data) for conn in connections], return_exceptions=True)

        # 统计失败的连接
        failed_count = sum(1 for result in results if isinstance(result, Exception))
        if failed_count > 0:
            logger.warning(f"Failed to send to {failed_count}/{len(connections)} connections")

    def get_all_sessions(self) -> list[str]:
        """获取所有活跃会话的 session_key 列表

        Returns:
            会话标识列表
        """
        return list(self.connections.keys())

    def get_connection_count(self, pipeline_uuid: str, session_type: str) -> int:
        """获取指定会话的连接数量

        Args:
            pipeline_uuid: 流水线 UUID
            session_type: 会话类型

        Returns:
            连接数量
        """
        session_key = f"{pipeline_uuid}:{session_type}"
        return len(self.connections.get(session_key, {}))

    async def cleanup_stale_connections(self, timeout_seconds: int = 120):
        """清理超时的连接

        Args:
            timeout_seconds: 超时时间（秒）
        """
        now = datetime.now()
        stale_connections = []

        # 查找超时连接
        for session_key, session_conns in self.connections.items():
            for conn_id, conn in session_conns.items():
                elapsed = (now - conn.last_ping).total_seconds()
                if elapsed > timeout_seconds:
                    stale_connections.append((conn_id, session_key))

        # 移除超时连接
        for conn_id, session_key in stale_connections:
            logger.warning(f"Removing stale connection: {conn_id} from {session_key}")
            await self.remove_connection(conn_id, session_key)

            # 尝试关闭 WebSocket
            try:
                conn = self.get_connection(conn_id, session_key)
                if conn:
                    await conn.websocket.close(1000, "Connection timeout")
            except Exception as e:
                logger.error(f"Error closing stale connection {conn_id}: {e}")

        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")
