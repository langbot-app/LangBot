from __future__ import annotations

import quart

from ... import group
from ....service.workflow import WorkflowExecutionFailedError


@group.group_class('workflows', '/api/v1/workflows')
class WorkflowsRouterGroup(group.RouterGroup):
    """Workflow API router group"""
    
    async def initialize(self) -> None:
        # Workflow CRUD
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                sort_by = quart.request.args.get('sort_by', 'created_at')
                sort_order = quart.request.args.get('sort_order', 'DESC')
                enabled_only = quart.request.args.get('enabled_only', 'false').lower() == 'true'
                return self.success(
                    data={'workflows': await self.ap.workflow_service.get_workflows(
                        sort_by, sort_order, enabled_only
                    )}
                )
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                workflow_uuid = await self.ap.workflow_service.create_workflow(json_data)
                return self.success(data={'uuid': workflow_uuid})

        # Get node types (available nodes for the editor)
        @self.route('/_/node-types', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data={
                'node_types': await self.ap.workflow_service.get_node_types(),
                'categories': await self.ap.workflow_service.get_node_types_by_category_meta(),
            })

        # Get node types by category
        @self.route('/_/node-types/categories', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data={'categories': await self.ap.workflow_service.get_node_types_by_category()})

        # Single workflow operations
        @self.route(
            '/<workflow_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str) -> str:
            if quart.request.method == 'GET':
                workflow = await self.ap.workflow_service.get_workflow(workflow_uuid)
                if workflow is None:
                    return self.http_status(404, -1, 'workflow not found')
                return self.success(data={'workflow': workflow})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                try:
                    await self.ap.workflow_service.update_workflow(workflow_uuid, json_data)
                    return self.success()
                except ValueError as e:
                    return self.http_status(404, -1, str(e))
            elif quart.request.method == 'DELETE':
                await self.ap.workflow_service.delete_workflow(workflow_uuid)
                return self.success()

        # Publish workflow (enable)
        @self.route('/<workflow_uuid>/publish', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            try:
                await self.ap.workflow_service.publish_workflow(workflow_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Unpublish workflow (disable)
        @self.route('/<workflow_uuid>/unpublish', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            try:
                await self.ap.workflow_service.unpublish_workflow(workflow_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Copy workflow
        @self.route('/<workflow_uuid>/copy', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            try:
                new_uuid = await self.ap.workflow_service.copy_workflow(workflow_uuid)
                return self.success(data={'uuid': new_uuid})
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Execute workflow manually
        @self.route('/<workflow_uuid>/execute', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            json_data = await quart.request.json or {}
            trigger_data = json_data.get('trigger_data', {})
            session_id = json_data.get('session_id')
            user_id = json_data.get('user_id')
            bot_id = json_data.get('bot_id')
            
            try:
                execution_id = await self.ap.workflow_service.execute_workflow(
                    workflow_uuid,
                    trigger_type='manual',
                    trigger_data=trigger_data,
                    session_id=session_id,
                    user_id=user_id,
                    bot_id=bot_id
                )
                return self.success(data={'execution_id': execution_id})
            except ValueError as e:
                return self.http_status(404, -1, str(e))
            except WorkflowExecutionFailedError as e:
                return self.http_status(500, -1, e.message)

        # Get workflow executions
        @self.route('/<workflow_uuid>/executions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            limit = int(quart.request.args.get('limit', 50))
            offset = int(quart.request.args.get('offset', 0))
            executions = await self.ap.workflow_service.get_executions(
                workflow_uuid=workflow_uuid,
                limit=limit,
                offset=offset
            )
            return self.success(data=executions)

        @self.route(
            '/<workflow_uuid>/executions/<execution_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            execution = await self.ap.workflow_service.get_execution(execution_uuid)
            if execution is None:
                return self.http_status(404, -1, 'execution not found')
            if execution.get('workflow_uuid') != workflow_uuid:
                return self.http_status(404, -1, 'execution not found in workflow')
            return self.success(data={'execution': execution})

        # Get workflow versions
        @self.route('/<workflow_uuid>/versions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            versions = await self.ap.workflow_service.get_versions(workflow_uuid)
            return self.success(data={'versions': versions})

        # Rollback to a specific version
        @self.route(
            '/<workflow_uuid>/rollback/<int:version>', 
            methods=['POST'], 
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, version: int) -> str:
            try:
                await self.ap.workflow_service.rollback_to_version(workflow_uuid, version)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Workflow extensions (plugins and MCP servers)
        @self.route(
            '/<workflow_uuid>/extensions', methods=['GET', 'PUT'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str) -> str:
            if quart.request.method == 'GET':
                workflow = await self.ap.workflow_service.get_workflow(workflow_uuid)
                if workflow is None:
                    return self.http_status(404, -1, 'workflow not found')

                # Get available plugins and MCP servers
                pipeline_component_kinds = ['Command', 'EventListener', 'Tool']
                plugins = await self.ap.plugin_connector.list_plugins(component_kinds=pipeline_component_kinds)
                mcp_servers = await self.ap.mcp_service.get_mcp_servers(contain_runtime_info=True)

                extensions_prefs = workflow.get('extensions_preferences', {})
                return self.success(
                    data={
                        'enable_all_plugins': extensions_prefs.get('enable_all_plugins', True),
                        'enable_all_mcp_servers': extensions_prefs.get('enable_all_mcp_servers', True),
                        'bound_plugins': extensions_prefs.get('plugins', []),
                        'available_plugins': plugins,
                        'bound_mcp_servers': extensions_prefs.get('mcp_servers', []),
                        'available_mcp_servers': mcp_servers,
                    }
                )
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                enable_all_plugins = json_data.get('enable_all_plugins', True)
                enable_all_mcp_servers = json_data.get('enable_all_mcp_servers', True)
                bound_plugins = json_data.get('bound_plugins', [])
                bound_mcp_servers = json_data.get('bound_mcp_servers', [])

                try:
                    await self.ap.workflow_service.update_workflow_extensions(
                        workflow_uuid, bound_plugins, bound_mcp_servers, 
                        enable_all_plugins, enable_all_mcp_servers
                    )
                    return self.success()
                except ValueError as e:
                    return self.http_status(404, -1, str(e))


        # Debug API - Start debug execution
        @self.route('/<workflow_uuid>/debug/start', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            json_data = await quart.request.json or {}
            context = json_data.get('context', {})
            variables = json_data.get('variables', {})
            breakpoints = json_data.get('breakpoints', [])
            
            try:
                execution_id = await self.ap.workflow_service.start_debug_execution(
                    workflow_uuid,
                    context=context,
                    variables=variables,
                    breakpoints=breakpoints
                )
                return self.success(data={'execution_id': execution_id})
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Debug API - Pause execution
        @self.route(
            '/<workflow_uuid>/debug/<execution_uuid>/pause',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            try:
                await self.ap.workflow_service.pause_debug_execution(workflow_uuid, execution_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Debug API - Resume execution
        @self.route(
            '/<workflow_uuid>/debug/<execution_uuid>/resume',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            try:
                await self.ap.workflow_service.resume_debug_execution(workflow_uuid, execution_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Debug API - Step execution
        @self.route(
            '/<workflow_uuid>/debug/<execution_uuid>/step',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            try:
                result = await self.ap.workflow_service.step_debug_execution(workflow_uuid, execution_uuid)
                return self.success(data=result)
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Debug API - Stop execution
        @self.route(
            '/<workflow_uuid>/debug/<execution_uuid>/stop',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            try:
                await self.ap.workflow_service.stop_debug_execution(workflow_uuid, execution_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Debug API - Get debug state
        @self.route(
            '/<workflow_uuid>/debug/<execution_uuid>/state',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            try:
                state = await self.ap.workflow_service.get_debug_state(workflow_uuid, execution_uuid)
                return self.success(data=state)
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Get execution logs
        @self.route(
            '/<workflow_uuid>/executions/<execution_uuid>/logs',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))
            try:
                result = await self.ap.workflow_service.get_execution_logs(
                    workflow_uuid, execution_uuid, limit, offset
                )
                return self.success(data=result)
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Rerun execution
        @self.route(
            '/<workflow_uuid>/executions/<execution_uuid>/rerun',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(workflow_uuid: str, execution_uuid: str) -> str:
            try:
                new_execution_id = await self.ap.workflow_service.rerun_execution(
                    workflow_uuid, execution_uuid
                )
                return self.success(data={'execution_uuid': new_execution_id})
            except ValueError as e:
                return self.http_status(404, -1, str(e))

        # Get workflow statistics
        @self.route('/<workflow_uuid>/stats', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(workflow_uuid: str) -> str:
            try:
                stats = await self.ap.workflow_service.get_workflow_stats(workflow_uuid)
                return self.success(data=stats)
            except ValueError as e:
                return self.http_status(404, -1, str(e))


@group.group_class('executions', '/api/v1/executions')
class ExecutionsRouterGroup(group.RouterGroup):
    """Workflow execution API router group"""
    
    async def initialize(self) -> None:
        # Get all executions (across all workflows)
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            limit = int(quart.request.args.get('limit', 50))
            offset = int(quart.request.args.get('offset', 0))
            status = quart.request.args.get('status')
            executions = await self.ap.workflow_service.get_executions(
                limit=limit,
                offset=offset,
                status=status
            )
            return self.success(data=executions)

        # Get single execution
        @self.route('/<execution_uuid>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(execution_uuid: str) -> str:
            execution = await self.ap.workflow_service.get_execution(execution_uuid)
            if execution is None:
                return self.http_status(404, -1, 'execution not found')
            return self.success(data={'execution': execution})

        # Cancel execution
        @self.route('/<execution_uuid>/cancel', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(execution_uuid: str) -> str:
            try:
                await self.ap.workflow_service.cancel_execution(execution_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(404, -1, str(e))
            except RuntimeError as e:
                return self.http_status(400, -1, str(e))
