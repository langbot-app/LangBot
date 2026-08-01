"""Authenticated dashboard WebSocket chat routes."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import typing
import uuid

import quart

from ....authz import Permission, permissions_for_role, require_permission
from ....context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from ... import group
from ......core.task_boundary import run_in_workspace_uow
from ......platform.sources.websocket_manager import WebSocketScope, ws_connection_manager
from ......utils import bounded_executor

logger = logging.getLogger(__name__)
_AUTH_TIMEOUT_SECONDS = 10.0
_DUPLEX_DRAIN_TIMEOUT_SECONDS = 0.25


def create_scoped_duplex_tasks(
    receive_coro: typing.Coroutine[typing.Any, typing.Any, None],
    send_coro: typing.Coroutine[typing.Any, typing.Any, None],
    workspace_uuid: str,
) -> tuple[asyncio.Task[None], asyncio.Task[None]]:
    """Create both socket directions under one trusted Workspace budget."""

    return (
        asyncio.create_task(
            bounded_executor.run_in_blocking_work_scope(
                receive_coro,
                workspace_uuid,
            )
        ),
        asyncio.create_task(
            bounded_executor.run_in_blocking_work_scope(
                send_coro,
                workspace_uuid,
            )
        ),
    )


async def wait_for_duplex_tasks(
    receive_task: asyncio.Task,
    send_task: asyncio.Task,
) -> None:
    """Stop the peer direction as soon as either socket task terminates."""

    try:
        done, _ = await asyncio.wait(
            {receive_task, send_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # A receive task may enqueue a terminal authorization/error frame and
        # then finish. Give the sender a short deterministic drain window
        # instead of cancelling it before that frame reaches the client.
        if receive_task in done and not send_task.done():
            await asyncio.wait(
                {send_task},
                timeout=_DUPLEX_DRAIN_TIMEOUT_SECONDS,
            )
    finally:
        for task in (receive_task, send_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(
            receive_task,
            send_task,
            return_exceptions=True,
        )


@group.group_class('websocket_chat', '/api/v1/pipelines/<pipeline_uuid>/ws')
class WebSocketChatRouterGroup(group.RouterGroup):
    async def _authenticate_websocket(self) -> tuple[RequestContext, str]:
        """Authenticate the first dashboard WebSocket message.

        Browsers cannot attach the normal Authorization/X-Workspace-Id headers
        to a WebSocket handshake.  The client therefore sends one auth frame
        immediately after opening the socket; no connection is registered and
        no runtime object is resolved before this method succeeds.
        """

        raw_message = await asyncio.wait_for(quart.websocket.receive(), timeout=_AUTH_TIMEOUT_SECONDS)
        payload = await asyncio.to_thread(json.loads, raw_message)
        if not isinstance(payload, dict) or payload.get('type') != 'authenticate':
            raise ValueError('Authentication is required')

        token = str(payload.get('token') or '').strip()
        workspace_uuid = str(payload.get('workspace_uuid') or '').strip()
        if not token or not workspace_uuid:
            raise ValueError('Authentication is required')

        support_context = await self._authenticate_support_admin(
            token,
            group.AuthType.USER_TOKEN,
            workspace_uuid=workspace_uuid,
            request_id=quart.websocket.headers.get('X-Request-Id') or str(uuid.uuid4()),
        )
        if support_context is not None:
            require_permission(support_context, Permission.RUNTIME_OPERATE)
            return support_context, token

        account, _ = await self._authenticate_account(token)
        account_uuid = getattr(account, 'uuid', None)
        collaboration_service = getattr(self.ap, 'workspace_collaboration_service', None)
        if not isinstance(account_uuid, str) or collaboration_service is None:
            raise ValueError('Workspace authentication is unavailable')

        access = await collaboration_service.resolve_account_workspace(account_uuid, workspace_uuid)
        request_context = RequestContext(
            instance_uuid=access.execution.instance_uuid,
            placement_generation=access.execution.placement_generation,
            request_id=quart.websocket.headers.get('X-Request-Id') or str(uuid.uuid4()),
            auth_type=group.AuthType.USER_TOKEN.value,
            principal=PrincipalContext(
                principal_type=PrincipalType.ACCOUNT,
                account_uuid=account_uuid,
            ),
            workspace=WorkspaceContext(
                workspace_uuid=access.workspace.uuid,
                membership_uuid=access.membership.uuid,
                role=access.membership.role,
                permissions=permissions_for_role(access.membership.role),
                membership_revision=access.membership.projection_revision,
            ),
        )
        require_permission(request_context, Permission.RUNTIME_OPERATE)
        return request_context, token

    async def _revalidate_websocket_authorization(
        self,
        request_context: RequestContext,
        token: str,
    ) -> RequestContext:
        """Recheck revocable account, membership, permission, and placement state."""

        if request_context.principal.principal_type == PrincipalType.SUPPORT_ADMIN:
            current_context = await self._authenticate_support_admin(
                token,
                group.AuthType.USER_TOKEN,
                workspace_uuid=request_context.workspace_uuid,
                request_id=request_context.request_id,
            )
            if current_context is None or current_context.principal != request_context.principal:
                raise ValueError('WebSocket support admin session changed')
            if (
                current_context.instance_uuid != request_context.instance_uuid
                or current_context.placement_generation != request_context.placement_generation
            ):
                raise ValueError('WebSocket authorization changed')
            require_permission(current_context, Permission.RUNTIME_OPERATE)
            return current_context

        account, _ = await self._authenticate_account(token)
        account_uuid = getattr(account, 'uuid', None)
        if account_uuid != request_context.account_uuid:
            raise ValueError('WebSocket account changed')

        collaboration_service = getattr(self.ap, 'workspace_collaboration_service', None)
        if collaboration_service is None or not isinstance(account_uuid, str):
            raise ValueError('Workspace authentication is unavailable')
        access = await collaboration_service.resolve_account_workspace(
            account_uuid,
            request_context.workspace_uuid,
        )
        if (
            access.workspace.uuid != request_context.workspace_uuid
            or access.membership.uuid != request_context.workspace.membership_uuid
            or access.membership.projection_revision != request_context.workspace.membership_revision
            or access.execution.instance_uuid != request_context.instance_uuid
            or access.execution.placement_generation != request_context.placement_generation
        ):
            raise ValueError('WebSocket authorization changed')

        current_context = RequestContext(
            instance_uuid=access.execution.instance_uuid,
            placement_generation=access.execution.placement_generation,
            request_id=request_context.request_id,
            auth_type=request_context.auth_type,
            principal=request_context.principal,
            workspace=WorkspaceContext(
                workspace_uuid=access.workspace.uuid,
                membership_uuid=access.membership.uuid,
                role=access.membership.role,
                permissions=permissions_for_role(access.membership.role),
                membership_revision=access.membership.projection_revision,
            ),
            entitlement_revision=request_context.entitlement_revision,
        )
        require_permission(current_context, Permission.RUNTIME_OPERATE)
        return current_context

    async def _get_scoped_adapter(self, request_context: RequestContext, pipeline_uuid: str):
        pipeline = await run_in_workspace_uow(
            self.ap,
            request_context.workspace_uuid,
            lambda: self.ap.pipeline_service.get_pipeline(request_context, pipeline_uuid),
        )
        if pipeline is None:
            return None
        proxy_bot = await self.ap.platform_mgr.get_websocket_proxy_bot(request_context)
        return proxy_bot.adapter

    async def initialize(self) -> None:
        @self.quart_app.websocket(self.path + '/connect')
        async def websocket_connect(pipeline_uuid: str):
            """Open one authenticated dashboard debug connection."""

            await quart.websocket.accept()
            try:
                request_context, token = await self._authenticate_websocket()
            except Exception:
                await quart.websocket.send(json.dumps({'type': 'error', 'message': 'Unauthorized'}))
                return

            session_type = quart.websocket.args.get('session_type', 'person')
            if session_type not in ['person', 'group']:
                await quart.websocket.send(
                    json.dumps({'type': 'error', 'message': 'session_type must be person or group'})
                )
                return

            try:
                websocket_adapter = await self._get_scoped_adapter(request_context, pipeline_uuid)
                if websocket_adapter is None:
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': 'Pipeline not found'}))
                    return

                connection = await ws_connection_manager.add_connection(
                    websocket=quart.websocket._get_current_object(),
                    scope=WebSocketScope.from_context(request_context),
                    pipeline_uuid=pipeline_uuid,
                    session_type=session_type,
                    trigger_principal=request_context.principal,
                    metadata={'user_agent': quart.websocket.headers.get('User-Agent', '')},
                    send_queue_size=(
                        self.ap.instance_config.data.get('system', {})
                        .get('websocket_retention', {})
                        .get('send_queue_size', 100)
                    ),
                    max_connections=(
                        self.ap.instance_config.data.get('system', {})
                        .get('websocket_retention', {})
                        .get('max_connections', 1024)
                    ),
                    max_connections_per_workspace=(
                        self.ap.instance_config.data.get('system', {})
                        .get('websocket_retention', {})
                        .get('max_connections_per_workspace', 32)
                    ),
                )

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
                    f'Dashboard WebSocket connected: {connection.connection_id} '
                    f'(workspace={connection.workspace_uuid}, pipeline={pipeline_uuid}, '
                    f'session_type={session_type})'
                )

                receive_task, send_task = create_scoped_duplex_tasks(
                    self._handle_receive(
                        connection,
                        websocket_adapter,
                        request_context,
                        token,
                    ),
                    self._handle_send(connection),
                    request_context.workspace_uuid,
                )
                try:
                    await wait_for_duplex_tasks(receive_task, send_task)
                except Exception as exc:
                    logger.error(f'WebSocket task execution error: {exc}')
                finally:
                    await ws_connection_manager.remove_connection(connection.connection_id)

            except Exception:
                logger.error('Dashboard WebSocket connection error', exc_info=True)
                try:
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': 'Internal server error'}))
                except Exception:
                    pass

        @self.route(
            '/messages/<session_type>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def get_messages(
            pipeline_uuid: str,
            session_type: str,
            request_context: RequestContext,
        ) -> str:
            if session_type not in ['person', 'group']:
                return self.http_status(400, -1, 'session_type must be person or group')

            websocket_adapter = await self._get_scoped_adapter(request_context, pipeline_uuid)
            if websocket_adapter is None:
                return self.http_status(404, -1, 'Pipeline not found')
            messages = websocket_adapter.get_websocket_messages(pipeline_uuid, session_type)
            return self.success(data={'messages': messages})

        @self.route(
            '/reset/<session_type>',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def reset_session(
            pipeline_uuid: str,
            session_type: str,
            request_context: RequestContext,
        ) -> str:
            if session_type not in ['person', 'group']:
                return self.http_status(400, -1, 'session_type must be person or group')

            websocket_adapter = await self._get_scoped_adapter(request_context, pipeline_uuid)
            if websocket_adapter is None:
                return self.http_status(404, -1, 'Pipeline not found')
            websocket_adapter.reset_session(pipeline_uuid, session_type)
            return self.success(data={'message': 'Session reset successfully'})

        @self.route(
            '/connections',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def get_connections(pipeline_uuid: str, request_context: RequestContext) -> str:
            if await self.ap.pipeline_service.get_pipeline(request_context, pipeline_uuid) is None:
                return self.http_status(404, -1, 'Pipeline not found')

            scope = WebSocketScope.from_context(request_context)
            stats = ws_connection_manager.get_stats(scope=scope)
            connections = await ws_connection_manager.get_connections_by_pipeline(
                pipeline_uuid,
                scope=scope,
            )
            return self.success(
                data={
                    'stats': stats,
                    'connections': [
                        {
                            'connection_id': connection.connection_id,
                            'session_type': connection.session_type,
                            'created_at': connection.created_at.isoformat(),
                            'last_active': connection.last_active.isoformat(),
                            'is_active': connection.is_active,
                        }
                        for connection in connections
                    ],
                }
            )

        @self.route(
            '/broadcast',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def broadcast_message(pipeline_uuid: str, request_context: RequestContext) -> str:
            if await self.ap.pipeline_service.get_pipeline(request_context, pipeline_uuid) is None:
                return self.http_status(404, -1, 'Pipeline not found')

            data = await quart.request.get_json()
            message = data.get('message')
            if not message:
                return self.http_status(400, -1, 'message is required')

            broadcast_data = {
                'type': 'broadcast',
                'message': message,
                'timestamp': datetime.datetime.now().isoformat(),
            }
            await ws_connection_manager.broadcast_to_pipeline(
                pipeline_uuid,
                broadcast_data,
                scope=WebSocketScope.from_context(request_context),
            )
            return self.success(data={'message': 'Broadcast sent successfully'})

    async def _handle_receive(
        self,
        connection,
        websocket_adapter,
        request_context: RequestContext,
        token: str,
    ):
        try:
            while connection.is_active:
                message = await quart.websocket.receive()
                await ws_connection_manager.update_activity(connection.connection_id)

                try:
                    data = await asyncio.to_thread(json.loads, message)
                    message_type = data.get('type', 'message')
                    if message_type == 'ping':
                        await connection.send_queue.put(
                            {'type': 'pong', 'timestamp': datetime.datetime.now().isoformat()}
                        )
                    elif message_type == 'message':
                        try:
                            request_context = await self._revalidate_websocket_authorization(request_context, token)
                        except Exception:
                            await connection.send_queue.put({'type': 'error', 'message': 'Unauthorized'})
                            break
                        await websocket_adapter.handle_websocket_message(connection, data)
                    elif message_type == 'disconnect':
                        break
                    else:
                        logger.warning(f'Unknown WebSocket message type: {message_type}')
                except json.JSONDecodeError:
                    await connection.send_queue.put({'type': 'error', 'message': 'Invalid JSON format'})

        except Exception:
            logger.error('Dashboard WebSocket receive error', exc_info=True)
        finally:
            connection.is_active = False
            try:
                connection.send_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def _handle_send(self, connection):
        try:
            while connection.is_active or not connection.send_queue.empty():
                try:
                    message = await asyncio.wait_for(connection.send_queue.get(), timeout=1.0)
                    if message is None:
                        break
                    encoded = await asyncio.to_thread(json.dumps, message)
                    await quart.websocket.send(encoded)
                except asyncio.TimeoutError:
                    continue
        except Exception:
            logger.error('Dashboard WebSocket send error', exc_info=True)
        finally:
            connection.is_active = False
