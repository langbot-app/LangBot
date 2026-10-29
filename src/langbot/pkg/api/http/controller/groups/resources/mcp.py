from __future__ import annotations

import quart
from urllib.parse import unquote

from ....authz import Permission
from ....context import RequestContext
from ......operation_trace import service as settings_service
from ......provider.tools.loaders.mcp_policy import MCPStdioDisabledError
from ... import group


@group.group_class('mcp', '/api/v1/mcp')
class MCPRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/servers',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            servers = await self.call_application('mcp.server.list', request_context, {'contain_runtime_info': True})
            return self.success(data={'servers': servers})

        @self.route(
            '/servers',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.json
            try:
                server_uuid = await self.call_application('mcp.server.create', request_context, {'server_data': data})
            except MCPStdioDisabledError as exc:
                return self.http_status(403, exc.code, str(exc))
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'uuid': server_uuid})

        @self.route(
            '/servers/<path:server_name>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            server_name = unquote(server_name)
            server_data = await self.call_application('mcp.server.get', request_context, {'server_name': server_name})
            if server_data is None:
                return self.http_status(404, -1, 'Server not found')
            return self.success(data={'server': server_data})

        @self.route(
            '/servers/<path:server_name>',
            methods=['PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            server_name = unquote(server_name)
            server_data = await self.call_application('mcp.server.get', request_context, {'server_name': server_name})
            if server_data is None:
                return self.http_status(404, -1, 'Server not found')
            # Name the MCP server in the trace, and for an update record which
            # fields actually moved so the card answers "what changed" rather
            # than only "the MCP config was touched".
            quart.g.operation_log_resource_id = server_name
            if quart.request.method == 'PUT':
                data = await quart.request.json
                try:
                    await self.call_application(
                        'mcp.server.update', request_context, {'server_uuid': server_data['uuid'], 'server_data': data}
                    )
                except MCPStdioDisabledError as exc:
                    return self.http_status(403, exc.code, str(exc))
                except ValueError as exc:
                    return self.http_status(400, -1, str(exc))
                changes = settings_service.changed_fields(
                    server_data,
                    data if isinstance(data, dict) else {},
                    ignore=('uuid',),
                )
                rule = settings_service.ACTION_RULES_BY_ACTION.get('mcp_config')
                quart.g.operation_log_changes = changes
                if rule is not None and changes:
                    quart.g.operation_log_summary = settings_service.build_summary(rule, changes)
            else:
                await self.call_application('mcp.server.delete', request_context, {'server_uuid': server_data['uuid']})
            return self.success()

        @self.route(
            '/servers/<path:server_name>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            """测试MCP服务器连接"""
            server_name = unquote(server_name)
            server_data = await quart.request.json
            try:
                task_id = await self.call_application(
                    'mcp.server.test', request_context, {'server_name': server_name, 'server_data': server_data}
                )
            except MCPStdioDisabledError as exc:
                return self.http_status(403, exc.code, str(exc))
            return self.success(data={'task_id': task_id})

        @self.route(
            '/servers/<path:server_name>/resources',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            """Get resources from an MCP server"""
            server_name = unquote(server_name)
            resources = await self.call_application('mcp.resource.list', request_context, {'server_name': server_name})
            templates = await self.call_application(
                'mcp.resource.templates', request_context, {'server_name': server_name}
            )
            runtime_info = await self.call_application(
                'mcp.server.runtime', request_context, {'server_name': server_name}
            )
            return self.success(
                data={
                    'resources': resources,
                    'resource_templates': templates,
                    'resource_capabilities': (runtime_info or {}).get('resource_capabilities', {}),
                }
            )

        @self.route(
            '/servers/<path:server_name>/resource-templates',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            """Get resource templates from an MCP server"""
            server_name = unquote(server_name)
            templates = await self.call_application(
                'mcp.resource.templates', request_context, {'server_name': server_name}
            )
            return self.success(data={'resource_templates': templates})

        @self.route(
            '/servers/<path:server_name>/logs',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            """Get logs from an MCP server"""
            server_name = unquote(server_name)
            try:
                limit = int(quart.request.args.get('limit', 200))
            except (TypeError, ValueError):
                limit = 200
            limit = min(limit, 500)
            level = quart.request.args.get('level') or None
            logs = await self.call_application(
                'mcp.server.logs', request_context, {'server_name': server_name, 'limit': limit, 'level': level}
            )
            return self.success(data={'logs': logs})

        @self.route(
            '/servers/<path:server_name>/resources/read',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            """Read a resource from an MCP server"""
            server_name = unquote(server_name)
            data = await quart.request.json
            uri = data.get('uri')
            if not uri:
                return self.http_status(400, -1, 'URI is required')
            envelope = await self.call_application(
                'mcp.resource.read',
                request_context,
                {
                    'server_name': server_name,
                    'uri': uri,
                    'max_bytes': data.get('max_bytes'),
                    'include_blob': bool(data.get('include_blob', False)),
                },
            )
            return self.success(data=envelope)
