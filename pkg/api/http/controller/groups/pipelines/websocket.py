"""流水线调试 WebSocket 路由

提供基于 WebSocket 的实时双向通信，用于流水线调试。
支持 person 和 group 两种会话类型的隔离。
"""

import asyncio
import logging
import uuid
from datetime import datetime

import quart

from ... import group
from ....service.websocket_pool import WebSocketConnection

logger = logging.getLogger(__name__)


async def handle_client_event(connection: WebSocketConnection, message: dict, ap):
    """处理客户端发送的事件

    Args:
        connection: WebSocket 连接对象
        message: 客户端消息 {'type': 'xxx', 'data': {...}}
        ap: Application 实例
    """
    event_type = message.get('type')
    data = message.get('data', {})

    pipeline_uuid = connection.pipeline_uuid
    session_type = connection.session_type

    try:
        webchat_adapter = ap.platform_mgr.webchat_proxy_bot.adapter

        if event_type == 'send_message':
            # 发送消息到指定会话
            message_chain_obj = data.get('message_chain', [])
            client_message_id = data.get('client_message_id')

            if not message_chain_obj:
                await connection.send('error', {'error': 'message_chain is required', 'error_code': 'INVALID_REQUEST'})
                return

            logger.info(
                f"Received send_message: pipeline={pipeline_uuid}, "
                f"session={session_type}, "
                f"client_msg_id={client_message_id}"
            )

            # 调用 webchat_adapter.send_webchat_message
            # 消息将通过 reply_message_chunk 自动推送到 WebSocket
            result = None
            async for msg in webchat_adapter.send_webchat_message(
                pipeline_uuid=pipeline_uuid, session_type=session_type, message_chain_obj=message_chain_obj, is_stream=True
            ):
                result = msg

            # 发送确认
            if result:
                await connection.send(
                    'message_sent',
                    {
                        'client_message_id': client_message_id,
                        'server_message_id': result.get('id'),
                        'timestamp': result.get('timestamp'),
                    },
                )

        elif event_type == 'load_history':
            # 加载指定会话的历史消息
            before_message_id = data.get('before_message_id')
            limit = data.get('limit', 50)

            logger.info(f"Loading history: pipeline={pipeline_uuid}, session={session_type}, limit={limit}")

            # 从对应会话获取历史消息
            messages = webchat_adapter.get_webchat_messages(pipeline_uuid, session_type)

            # 简单分页：返回最后 limit 条
            if before_message_id:
                # TODO: 实现基于 message_id 的分页
                history_messages = messages[-limit:]
            else:
                history_messages = messages[-limit:] if len(messages) > limit else messages

            await connection.send(
                'history', {'messages': history_messages, 'has_more': len(messages) > len(history_messages)}
            )

        elif event_type == 'interrupt':
            # 中断消息
            message_id = data.get('message_id')
            logger.info(f"Interrupt requested: message_id={message_id}")

            # TODO: 实现中断逻辑
            await connection.send('interrupted', {'message_id': message_id, 'partial_content': ''})

        elif event_type == 'ping':
            # 心跳
            connection.last_ping = datetime.now()
            await connection.send('pong', {'timestamp': data.get('timestamp')})

        else:
            logger.warning(f"Unknown event type: {event_type}")
            await connection.send('error', {'error': f'Unknown event type: {event_type}', 'error_code': 'UNKNOWN_EVENT'})

    except Exception as e:
        logger.error(f"Error handling event {event_type}: {e}", exc_info=True)
        await connection.send(
            'error',
            {'error': f'Internal server error: {str(e)}', 'error_code': 'INTERNAL_ERROR', 'details': {'event_type': event_type}},
        )


@group.group_class('pipeline-websocket', '/api/v1/pipelines/<pipeline_uuid>/chat')
class PipelineWebSocketRouterGroup(group.RouterGroup):
    """流水线调试 WebSocket 路由组"""

    async def initialize(self) -> None:
        @self.route('/ws')
        async def websocket_handler(pipeline_uuid: str):
            """WebSocket 连接处理 - 会话隔离

            连接流程:
                1. 客户端建立 WebSocket 连接
                2. 客户端发送 connect 事件（携带 session_type 和 token）
                3. 服务端验证并创建连接对象
                4. 进入消息循环，处理客户端事件
                5. 断开时清理连接

            Args:
                pipeline_uuid: 流水线 UUID
            """
            websocket = quart.websocket._get_current_object()
            connection_id = str(uuid.uuid4())
            session_key = None
            connection = None

            try:
                # 1. 等待客户端发送 connect 事件
                first_message = await websocket.receive_json()

                if first_message.get('type') != 'connect':
                    await websocket.send_json(
                        {'type': 'error', 'data': {'error': 'First message must be connect event', 'error_code': 'INVALID_HANDSHAKE'}}
                    )
                    await websocket.close(1008)
                    return

                connect_data = first_message.get('data', {})
                session_type = connect_data.get('session_type')
                token = connect_data.get('token')

                # 验证参数
                if session_type not in ['person', 'group']:
                    await websocket.send_json(
                        {'type': 'error', 'data': {'error': 'session_type must be person or group', 'error_code': 'INVALID_SESSION_TYPE'}}
                    )
                    await websocket.close(1008)
                    return

                # 验证 token
                if not token:
                    await websocket.send_json(
                        {'type': 'error', 'data': {'error': 'token is required', 'error_code': 'MISSING_TOKEN'}}
                    )
                    await websocket.close(1008)
                    return

                # 验证用户身份
                try:
                    user = await self.ap.user_service.verify_token(token)
                    if not user:
                        await websocket.send_json({'type': 'error', 'data': {'error': 'Unauthorized', 'error_code': 'UNAUTHORIZED'}})
                        await websocket.close(1008)
                        return
                except Exception as e:
                    logger.error(f"Token verification failed: {e}")
                    await websocket.send_json(
                        {'type': 'error', 'data': {'error': 'Token verification failed', 'error_code': 'AUTH_ERROR'}}
                    )
                    await websocket.close(1008)
                    return

                # 2. 创建连接对象并加入连接池
                connection = WebSocketConnection(
                    connection_id=connection_id,
                    websocket=websocket,
                    pipeline_uuid=pipeline_uuid,
                    session_type=session_type,
                    created_at=datetime.now(),
                    last_ping=datetime.now(),
                )

                session_key = connection.session_key
                ws_pool = self.ap.ws_pool
                ws_pool.add_connection(connection)

                # 3. 发送连接成功事件
                await connection.send(
                    'connected', {'connection_id': connection_id, 'session_type': session_type, 'pipeline_uuid': pipeline_uuid}
                )

                logger.info(f"WebSocket connected: {connection_id} [pipeline={pipeline_uuid}, session={session_type}]")

                # 4. 进入消息处理循环
                while True:
                    try:
                        message = await websocket.receive_json()
                        await handle_client_event(connection, message, self.ap)
                    except asyncio.CancelledError:
                        logger.info(f"WebSocket connection cancelled: {connection_id}")
                        break
                    except Exception as e:
                        logger.error(f"Error receiving message from {connection_id}: {e}")
                        break

            except quart.exceptions.WebsocketDisconnected:
                logger.info(f"WebSocket disconnected: {connection_id}")
            except Exception as e:
                logger.error(f"WebSocket error for {connection_id}: {e}", exc_info=True)
            finally:
                # 清理连接
                if connection and session_key:
                    ws_pool = self.ap.ws_pool
                    await ws_pool.remove_connection(connection_id, session_key)
                    logger.info(f"WebSocket connection cleaned up: {connection_id}")
