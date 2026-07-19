"""WebSocket连接管理器 - 管理多个并发WebSocket连接"""

import asyncio
import dataclasses
import logging
import typing
import uuid
from datetime import datetime

import pydantic

from ...api.http.context import ExecutionContext

logger = logging.getLogger(__name__)
_SESSION_FILTER_UNSET = object()


@dataclasses.dataclass(frozen=True, slots=True)
class WebSocketScope:
    """Trusted runtime placement carried by every WebSocket connection."""

    instance_uuid: str
    workspace_uuid: str
    placement_generation: int

    def __post_init__(self) -> None:
        if not self.instance_uuid.strip() or not self.workspace_uuid.strip():
            raise ValueError('WebSocket scope requires an instance and Workspace')
        if self.placement_generation <= 0:
            raise ValueError('WebSocket scope requires a positive placement generation')

    @classmethod
    def from_context(cls, context: typing.Any) -> 'WebSocketScope':
        return cls(
            instance_uuid=str(getattr(context, 'instance_uuid', '')),
            workspace_uuid=str(getattr(context, 'workspace_uuid', '')),
            placement_generation=int(getattr(context, 'placement_generation', 0)),
        )


def is_valid_session_id(value: str) -> bool:
    """Accept only canonical random UUIDs for client conversation identifiers."""
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return parsed.version == 4 and str(parsed) == value


class WebSocketConnection(pydantic.BaseModel):
    """单个WebSocket连接"""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    connection_id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
    """连接唯一ID"""

    instance_uuid: str
    """Owning LangBot instance."""

    workspace_uuid: str
    """Owning Workspace."""

    placement_generation: int
    """Workspace placement generation captured at connect time."""

    pipeline_uuid: str
    """关联的流水线UUID"""

    session_type: str  # 'person' or 'group'
    """会话类型"""

    session_id: str | None = None
    """Optional client conversation identifier used by embed widgets."""

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

    @property
    def scope(self) -> WebSocketScope:
        return WebSocketScope(
            instance_uuid=self.instance_uuid,
            workspace_uuid=self.workspace_uuid,
            placement_generation=self.placement_generation,
        )

    @property
    def execution_context(self) -> ExecutionContext:
        """Return the storage/runtime context captured for this connection."""

        return ExecutionContext(
            instance_uuid=self.instance_uuid,
            workspace_uuid=self.workspace_uuid,
            placement_generation=self.placement_generation,
            pipeline_uuid=self.pipeline_uuid,
        )


class WebSocketConnectionManager:
    """WebSocket连接管理器 - 支持多连接并发"""

    def __init__(self):
        self.connections: dict[str, WebSocketConnection] = {}
        """所有活跃连接 {connection_id: connection}"""

        self.pipeline_connections: dict[tuple[str, str, int, str], set[str]] = {}
        """Scoped pipeline to connection mapping."""

        self.session_connections: dict[tuple[str, str, int, str], set[str]] = {}
        """Scoped session-type to connection mapping."""

        self._lock = asyncio.Lock()
        """线程锁，保护并发访问"""

    async def add_connection(
        self,
        websocket: typing.Any,
        scope: WebSocketScope,
        pipeline_uuid: str,
        session_type: str,
        metadata: dict | None = None,
        session_id: str | None = None,
    ) -> WebSocketConnection:
        """Register a WebSocket connection and its optional embed session."""
        async with self._lock:
            connection = WebSocketConnection(
                instance_uuid=scope.instance_uuid,
                workspace_uuid=scope.workspace_uuid,
                placement_generation=scope.placement_generation,
                pipeline_uuid=pipeline_uuid,
                session_type=session_type,
                session_id=session_id,
                websocket=websocket,
                metadata=metadata or {},
            )

            self.connections[connection.connection_id] = connection

            # 更新流水线映射
            pipeline_key = self._pipeline_key(scope, pipeline_uuid)
            if pipeline_key not in self.pipeline_connections:
                self.pipeline_connections[pipeline_key] = set()
            self.pipeline_connections[pipeline_key].add(connection.connection_id)

            # 更新会话类型映射
            session_key = self._session_key(scope, session_type)
            if session_key not in self.session_connections:
                self.session_connections[session_key] = set()
            self.session_connections[session_key].add(connection.connection_id)

            logger.debug(
                f'WebSocket connection established: {connection.connection_id} '
                f'(workspace={scope.workspace_uuid}, generation={scope.placement_generation}, '
                f'pipeline={pipeline_uuid}, session_type={session_type})'
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
            pipeline_key = self._pipeline_key(connection.scope, connection.pipeline_uuid)
            if pipeline_key in self.pipeline_connections:
                self.pipeline_connections[pipeline_key].discard(connection_id)
                if not self.pipeline_connections[pipeline_key]:
                    del self.pipeline_connections[pipeline_key]

            # 从会话类型映射中移除
            session_key = self._session_key(connection.scope, connection.session_type)
            if session_key in self.session_connections:
                self.session_connections[session_key].discard(connection_id)
                if not self.session_connections[session_key]:
                    del self.session_connections[session_key]

            del self.connections[connection_id]

            logger.debug(f'WebSocket connection disconnected: {connection_id}')

    @staticmethod
    def _pipeline_key(scope: WebSocketScope, pipeline_uuid: str) -> tuple[str, str, int, str]:
        return (
            scope.instance_uuid,
            scope.workspace_uuid,
            scope.placement_generation,
            pipeline_uuid,
        )

    @staticmethod
    def _session_key(scope: WebSocketScope, session_type: str) -> tuple[str, str, int, str]:
        return (
            scope.instance_uuid,
            scope.workspace_uuid,
            scope.placement_generation,
            session_type,
        )

    async def get_connection(
        self,
        connection_id: str,
        *,
        scope: WebSocketScope,
    ) -> WebSocketConnection | None:
        """Get a connection only when it belongs to the expected placement."""

        connection = self.connections.get(connection_id)
        if connection is None or connection.scope != scope:
            return None
        return connection

    async def get_connection_by_session_id(
        self,
        session_id: str,
        *,
        scope: WebSocketScope,
        pipeline_uuid: str | None = None,
    ) -> WebSocketConnection | None:
        """Get an active embed connection by its stable browser session identifier."""
        for connection in self.connections.values():
            if (
                connection.session_id == session_id
                and connection.is_active
                and connection.scope == scope
                and (pipeline_uuid is None or connection.pipeline_uuid == pipeline_uuid)
            ):
                return connection
        return None

    async def get_connections_by_pipeline(
        self,
        pipeline_uuid: str,
        *,
        scope: WebSocketScope,
    ) -> list[WebSocketConnection]:
        """获取指定流水线的所有连接"""
        connection_ids = self.pipeline_connections.get(self._pipeline_key(scope, pipeline_uuid), set())
        return [self.connections[cid] for cid in connection_ids if cid in self.connections]

    async def get_connections_by_session_type(
        self,
        session_type: str,
        *,
        scope: WebSocketScope,
    ) -> list[WebSocketConnection]:
        """获取指定会话类型的所有连接"""
        connection_ids = self.session_connections.get(self._session_key(scope, session_type), set())
        return [self.connections[cid] for cid in connection_ids if cid in self.connections]

    async def broadcast_to_pipeline(
        self,
        pipeline_uuid: str,
        message: dict,
        *,
        scope: WebSocketScope,
        session_type: str | None = None,
        session_id: typing.Any = _SESSION_FILTER_UNSET,
    ):
        """Broadcast a message to matching connections for one pipeline.

        Args:
            pipeline_uuid: Pipeline identifier.
            message: Serialized message to enqueue.
            session_type: Optional session-type filter.
            session_id: Embed conversation filter. Omit it to broadcast across
                conversations; pass ``None`` to target non-embed connections.
        """
        connections = await self.get_connections_by_pipeline(pipeline_uuid, scope=scope)

        if session_type is not None:
            connections = [conn for conn in connections if conn.session_type == session_type]

        if session_id is not _SESSION_FILTER_UNSET:
            connections = [conn for conn in connections if conn.session_id == session_id]

        tasks = []
        for conn in connections:
            tasks.append(self.send_to_connection(conn.connection_id, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to_connection(self, connection_id: str, message: dict):
        """向指定连接发送消息"""
        connection = self.connections.get(connection_id)
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
        connection = self.connections.get(connection_id)
        if connection:
            connection.last_active = datetime.now()

    def get_stats(self, *, scope: WebSocketScope) -> dict:
        """Return connection statistics for one trusted placement."""

        scoped_connections = [connection for connection in self.connections.values() if connection.scope == scope]
        pipelines: dict[str, int] = {}
        session_types: dict[str, int] = {}
        for connection in scoped_connections:
            pipelines[connection.pipeline_uuid] = pipelines.get(connection.pipeline_uuid, 0) + 1
            session_types[connection.session_type] = session_types.get(connection.session_type, 0) + 1
        return {
            'total_connections': len(scoped_connections),
            'pipelines': len(pipelines),
            'connections_by_pipeline': pipelines,
            'connections_by_session_type': session_types,
        }


# 全局连接管理器实例
ws_connection_manager = WebSocketConnectionManager()
