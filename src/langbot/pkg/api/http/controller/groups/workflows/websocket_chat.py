"""Workflow WebSocket聊天路由 - 支持工作流调试的双向实时通信"""

import asyncio
import datetime
import json
import logging

import quart

from ... import group
from ......platform.sources.websocket_manager import ws_connection_manager

logger = logging.getLogger(__name__)


@group.group_class('workflow_websocket_chat', '/api/v1/workflows/<workflow_uuid>/ws')
class WorkflowWebSocketChatRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.quart_app.websocket(self.path + '/connect')
        async def workflow_websocket_connect(workflow_uuid: str):
            """
            建立工作流WebSocket连接

            URL参数:
                - workflow_uuid: 工作流UUID
                - session_type: 会话类型 (person/group)
            """
            try:
                session_type = quart.websocket.args.get('session_type', 'person')
                logger.info(
                    'Workflow WebSocket connect request received',
                    extra={
                        'workflow_uuid': workflow_uuid,
                        'session_type': session_type,
                        'path': quart.websocket.path,
                        'query_string': quart.websocket.query_string.decode('utf-8', errors='ignore'),
                        'remote_addr': getattr(quart.websocket, 'remote_addr', None),
                        'user_agent': quart.websocket.headers.get('User-Agent', ''),
                        'host': quart.websocket.headers.get('Host', ''),
                        'origin': quart.websocket.headers.get('Origin', ''),
                    },
                )
 
                if session_type not in ['person', 'group']:
                    await quart.websocket.send(
                        json.dumps({'type': 'error', 'message': 'session_type must be person or group'})
                    )
                    return

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter
 
                if not websocket_adapter:
                    logger.warning(
                        'Workflow WebSocket adapter missing',
                        extra={
                            'workflow_uuid': workflow_uuid,
                            'session_type': session_type,
                        },
                    )
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': 'WebSocket adapter not found'}))
                    return

                connection = await ws_connection_manager.add_connection(
                    websocket=quart.websocket._get_current_object(),
                    pipeline_uuid=workflow_uuid,
                    session_type=session_type,
                    metadata={'user_agent': quart.websocket.headers.get('User-Agent', ''), 'is_workflow': True},
                )

                await quart.websocket.send(
                    json.dumps(
                        {
                            'type': 'connected',
                            'connection_id': connection.connection_id,
                            'workflow_uuid': workflow_uuid,
                            'session_type': session_type,
                            'timestamp': connection.created_at.isoformat(),
                        }
                    )
                )

                logger.debug(
                    f'Workflow WebSocket connection established: {connection.connection_id} '
                    f'(workflow={workflow_uuid}, session_type={session_type})'
                )

                receive_task = asyncio.create_task(self._handle_receive(connection, websocket_adapter))
                send_task = asyncio.create_task(self._handle_send(connection))

                try:
                    await asyncio.gather(receive_task, send_task)
                except Exception as e:
                    logger.error(f'Workflow WebSocket task execution error: {e}')
                finally:
                    await ws_connection_manager.remove_connection(connection.connection_id)
                    logger.debug(f'Workflow WebSocket connection cleaned: {connection.connection_id}')

            except Exception as e:
                logger.error(
                    'Workflow WebSocket connection error',
                    exc_info=True,
                    extra={
                        'workflow_uuid': workflow_uuid,
                        'session_type': quart.websocket.args.get('session_type', 'person'),
                        'path': quart.websocket.path,
                        'query_string': quart.websocket.query_string.decode('utf-8', errors='ignore'),
                        'remote_addr': getattr(quart.websocket, 'remote_addr', None),
                    },
                )
                try:
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': str(e)}))
                except:
                    pass

        @self.route('/messages/<session_type>', methods=['GET'])
        async def get_messages(workflow_uuid: str, session_type: str) -> str:
            """获取工作流消息历史"""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    return self.http_status(404, -1, 'WebSocket adapter not found')

                messages = websocket_adapter.get_websocket_messages(workflow_uuid, session_type)

                return self.success(data={'messages': messages})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/reset/<session_type>', methods=['POST'])
        async def reset_session(workflow_uuid: str, session_type: str) -> str:
            """重置工作流会话"""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    return self.http_status(404, -1, 'WebSocket adapter not found')

                websocket_adapter.reset_session(workflow_uuid, session_type)

                return self.success(data={'message': 'Session reset successfully'})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/connections', methods=['GET'])
        async def get_connections(workflow_uuid: str) -> str:
            """获取当前工作流连接统计"""
            try:
                stats = ws_connection_manager.get_stats()
                connections = await ws_connection_manager.get_connections_by_pipeline(workflow_uuid)

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
        async def broadcast_message(workflow_uuid: str) -> str:
            """向所有工作流连接广播消息"""
            try:
                data = await quart.request.get_json()
                message = data.get('message')

                if not message:
                    return self.http_status(400, -1, 'message is required')

                broadcast_data = {
                    'type': 'broadcast',
                    'message': message,
                    'timestamp': datetime.datetime.now().isoformat(),
                }

                await ws_connection_manager.broadcast_to_pipeline(workflow_uuid, broadcast_data)

                return self.success(data={'message': 'Broadcast sent successfully'})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

    async def _handle_receive(self, connection, websocket_adapter):
        """处理接收消息的任务"""
        try:
            while connection.is_active:
                message = await quart.websocket.receive()

                await ws_connection_manager.update_activity(connection.connection_id)

                try:
                    data = json.loads(message)
                    message_type = data.get('type', 'message')

                    if message_type == 'ping':
                        await connection.send_queue.put(
                            {'type': 'pong', 'timestamp': datetime.datetime.now().isoformat()}
                        )

                    elif message_type == 'message':
                        logger.debug(f'收到工作流消息: {data} from {connection.connection_id}')
                        await websocket_adapter.handle_websocket_message(connection, data)

                    elif message_type == 'disconnect':
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
                try:
                    message = await asyncio.wait_for(connection.send_queue.get(), timeout=1.0)
                    await quart.websocket.send(json.dumps(message))

                except asyncio.TimeoutError:
                    continue

        except Exception as e:
            logger.error(f'Send message error: {e}', exc_info=True)
        finally:
            connection.is_active = False
