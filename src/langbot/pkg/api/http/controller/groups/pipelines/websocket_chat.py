"""WebSocket聊天路由 - 支持双向实时通信"""

import asyncio
import datetime
import json
import logging

import quart

from ... import group
from ......platform.sources.websocket_manager import ws_connection_manager

logger = logging.getLogger(__name__)


@group.group_class('websocket_chat', '/api/v1/pipelines/<pipeline_uuid>/ws')
class WebSocketChatRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        # 直接使用 quart_app 注册 WebSocket 路由
        @self.quart_app.websocket(self.path + '/connect')
        async def websocket_connect(pipeline_uuid: str):
            """
            建立WebSocket连接

            URL参数:
                - pipeline_uuid: 流水线UUID
                - session_type: 会话类型 (person/group)
            """
            try:
                # 获取参数 - 在WebSocket上下文中使用 quart.websocket.args
                session_type = quart.websocket.args.get('session_type', 'person')

                if session_type not in ['person', 'group']:
                    await quart.websocket.send(
                        json.dumps({'type': 'error', 'message': 'session_type must be person or group'})
                    )
                    return

                # 获取WebSocket适配器
                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': 'WebSocket adapter not found'}))
                    return

                # 注册连接
                connection = await ws_connection_manager.add_connection(
                    websocket=quart.websocket._get_current_object(),
                    pipeline_uuid=pipeline_uuid,
                    session_type=session_type,
                    metadata={'user_agent': quart.websocket.headers.get('User-Agent', '')},
                )

                # 发送连接成功消息
                await quart.websocket.send(
                    json.dumps(
                        {
                            'type': 'connected',
                            'connection_id': connection.connection_id,
                            'pipeline_uuid': pipeline_uuid,
                            'session_type': session_type,
                            'timestamp': connection.created_at.isoformat(),
                        }
                    )
                )

                logger.debug(
                    f'WebSocket connection established: {connection.connection_id} '
                    f'(pipeline={pipeline_uuid}, session_type={session_type})'
                )

                # 创建接收和发送任务
                receive_task = asyncio.create_task(self._handle_receive(connection, websocket_adapter))
                send_task = asyncio.create_task(self._handle_send(connection))

                # 等待任务完成
                try:
                    await asyncio.gather(receive_task, send_task)
                except Exception as e:
                    logger.error(f'WebSocket task execution error: {e}')
                finally:
                    # 清理连接
                    await ws_connection_manager.remove_connection(connection.connection_id)
                    logger.debug(f'WebSocket connection cleaned: {connection.connection_id}')

            except Exception as e:
                logger.error(f'WebSocket connection error: {e}', exc_info=True)
                try:
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': str(e)}))
                except:
                    pass

        @self.route('/messages/<session_type>', methods=['GET'])
        async def get_messages(pipeline_uuid: str, session_type: str) -> str:
            """获取消息历史"""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    return self.http_status(404, -1, 'WebSocket adapter not found')

                messages = websocket_adapter.get_websocket_messages(pipeline_uuid, session_type)

                return self.success(data={'messages': messages})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/reset/<session_type>', methods=['POST'])
        async def reset_session(pipeline_uuid: str, session_type: str) -> str:
            """重置会话"""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    return self.http_status(404, -1, 'WebSocket adapter not found')

                websocket_adapter.reset_session(pipeline_uuid, session_type)

                return self.success(data={'message': 'Session reset successfully'})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/connections', methods=['GET'])
        async def get_connections(pipeline_uuid: str) -> str:
            """获取当前连接统计"""
            try:
                stats = ws_connection_manager.get_stats()
                connections = await ws_connection_manager.get_connections_by_pipeline(pipeline_uuid)

                return self.success(
                    data={
                        'stats': stats,
                        'connections': [
                            {
                                'connection_id': conn.connection_id,
                                'session_type': conn.session_type,
                                'created_at': conn.created_at.isoformat(),
                                'last_active': conn.last_active.isoformat(),
                                'is_active': conn.is_active,
                            }
                            for conn in connections
                        ],
                    }
                )

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/broadcast', methods=['POST'])
        async def broadcast_message(pipeline_uuid: str) -> str:
            """向所有连接广播消息（后端主动推送）"""
            try:
                data = await quart.request.get_json()
                message = data.get('message')

                if not message:
                    return self.http_status(400, -1, 'message is required')

                # 广播消息
                broadcast_data = {
                    'type': 'broadcast',
                    'message': message,
                    'timestamp': datetime.datetime.now().isoformat(),
                }

                await ws_connection_manager.broadcast_to_pipeline(pipeline_uuid, broadcast_data)

                return self.success(data={'message': 'Broadcast sent successfully'})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

    async def _handle_receive(self, connection, websocket_adapter):
        """处理接收消息的任务"""
        try:
            while connection.is_active:
                # 接收消息
                message = await quart.websocket.receive()

                # 更新活跃时间
                await ws_connection_manager.update_activity(connection.connection_id)

                try:
                    data = json.loads(message)
                    message_type = data.get('type', 'message')

                    if message_type == 'ping':
                        # 心跳响应
                        await connection.send_queue.put(
                            {'type': 'pong', 'timestamp': datetime.datetime.now().isoformat()}
                        )

                    elif message_type == 'message':
                        # 处理用户消息
                        logger.debug(f'收到消息: {data} from {connection.connection_id}')

                        # 处理消息（不等待响应，响应会通过broadcast异步发送）
                        await websocket_adapter.handle_websocket_message(connection, data)

                    elif message_type == 'disconnect':
                        # 客户端主动断开
                        logger.debug(f'Client disconnected: {connection.connection_id}')
                        break

                    else:
                        logger.warning(f'Unknown message type: {message_type}')

                except json.JSONDecodeError:
                    logger.error(f'Invalid JSON message: {message}')
                    await connection.send_queue.put({'type': 'error', 'message': 'Invalid JSON format'})

        except Exception as e:
            logger.error(f'Receive message error: {e}', exc_info=True)
        finally:
            connection.is_active = False

    async def _handle_send(self, connection):
        """处理发送消息的任务"""
        try:
            while connection.is_active:
                # 从队列获取消息
                try:
                    message = await asyncio.wait_for(connection.send_queue.get(), timeout=1.0)

                    # 发送消息
                    await quart.websocket.send(json.dumps(message))

                except asyncio.TimeoutError:
                    # 超时继续循环
                    continue

        except Exception as e:
            logger.error(f'Send message error: {e}', exc_info=True)
        finally:
            connection.is_active = False
