from __future__ import annotations

import hmac

import quart

from ....authz import Permission, has_permission
from ....service.secrets import redact_secrets
from ....context import RequestContext
from ....service.workflow_run import run_workflow
from ... import group


@group.group_class('workflows', '/api/v1/workflows')
class WorkflowsRouterGroup(group.RouterGroup):
    def _read_response(self, context: RequestContext, *, data: dict) -> str:
        if not has_permission(context, Permission.RESOURCE_MANAGE):
            data = redact_secrets(data)
        return self.success(data=data)

    async def initialize(self) -> None:
        @self.route(
            '/hooks/<bot_uuid>/<workflow_uuid>/<secret>',
            methods=['POST'],
            auth_type=group.AuthType.NONE,
        )
        async def _(bot_uuid: str, workflow_uuid: str, secret: str) -> str:
            from ....service.workflow import WorkflowExecutionFailedError

            if (quart.request.content_length or 0) > 256 * 1024:
                return self.http_status(413, -1, 'Payload too large')
            payload = await quart.request.get_json(silent=True)
            if payload is None:
                payload = {}
            if not isinstance(payload, dict):
                return self.http_status(400, -1, 'The webhook body must be a JSON object')
            bot = next(
                (item for item in tuple(self.ap.platform_mgr.bots) if item.bot_entity.uuid == bot_uuid and item.enable),
                None,
            )
            if bot is None:
                return self.http_status(404, -1, 'Webhook not found')

            async def run():
                workflow = await self.ap.workflow_service.get_workflow(bot.execution_context, workflow_uuid)
                if not workflow or not workflow.get('is_enabled', True):
                    return None
                if not any(
                    trigger.get('type') == 'webhook'
                    and trigger.get('bot_uuid') == bot_uuid
                    and hmac.compare_digest(str(trigger.get('secret', '')), secret)
                    for trigger in workflow.get('triggers') or []
                ):
                    return None
                try:
                    execution_uuid, _ = await bot.run_triggered_workflow(workflow, 'webhook', {'payload': payload})
                    return {'execution_uuid': execution_uuid, 'status': 'completed'}
                except WorkflowExecutionFailedError as exc:
                    return {'execution_uuid': exc.execution_id, 'status': 'failed', 'error': exc.message}

            result = await bot._run_event_delivery(run)
            if result is None:
                return self.http_status(404, -1, 'Webhook not found')
            return self.success(data=result)

        @self.route(
            '', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY, permission=Permission.RESOURCE_VIEW
        )
        async def _(request_context: RequestContext) -> str:
            return self._read_response(
                request_context,
                data={
                    'workflows': await self.ap.workflow_service.get_workflows(
                        request_context,
                        quart.request.args.get('sort_by', 'created_at'),
                        quart.request.args.get('sort_order', 'DESC'),
                    )
                },
            )

        @self.route(
            '', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY, permission=Permission.RESOURCE_MANAGE
        )
        async def _(request_context: RequestContext) -> str:
            try:
                workflow_uuid = await self.ap.workflow_service.create_workflow(
                    request_context, await quart.request.json
                )
                return self.success(
                    data=await self.ap.workflow_service.workflow_response(request_context, workflow_uuid)
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/_/node-types',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self._read_response(
                request_context,
                data={
                    'node_types': await self.ap.workflow_service.get_node_types(),
                },
            )

        @self.route(
            '/<workflow_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            workflow = await self.ap.workflow_service.get_workflow(request_context, workflow_uuid)
            if workflow is None:
                return self.http_status(404, -1, 'Workflow not found')
            return self._read_response(
                request_context,
                data={
                    'workflow': workflow,
                    'issues': await self.ap.workflow_service.validate_graph(request_context, workflow['graph']),
                },
            )

        @self.route(
            '/<workflow_uuid>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.ap.workflow_service.update_workflow(request_context, workflow_uuid, await quart.request.json)
                return self.success(
                    data=await self.ap.workflow_service.workflow_response(request_context, workflow_uuid)
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<workflow_uuid>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.ap.workflow_service.delete_workflow(request_context, workflow_uuid)
                return self.success()
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<workflow_uuid>/copy',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            try:
                return self.success(
                    data=await self.ap.workflow_service.workflow_response(
                        request_context, await self.ap.workflow_service.copy_workflow(request_context, workflow_uuid)
                    )
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<workflow_uuid>/executions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            try:
                limit = min(max(int(quart.request.args.get('limit', 50)), 1), 100)
                offset = max(int(quart.request.args.get('offset', 0)), 0)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self._read_response(
                request_context,
                data=await self.ap.workflow_service.get_executions(
                    request_context, workflow_uuid, limit, offset, quart.request.args.get('status')
                ),
            )

        @self.route(
            '/<workflow_uuid>/executions/<execution_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(workflow_uuid: str, execution_uuid: str, request_context: RequestContext) -> str:
            execution = await self.ap.workflow_service.get_execution(request_context, workflow_uuid, execution_uuid)
            if execution is None:
                return self.http_status(404, -1, 'Execution not found')
            return self._read_response(request_context, data={'execution': execution})

        @self.route(
            '/<workflow_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            payload = await quart.request.json
            try:
                return self._read_response(
                    request_context,
                    data=await run_workflow(
                        self.ap,
                        request_context,
                        workflow_uuid,
                        payload.get('text'),
                        graph=payload.get('graph'),
                        session_type=payload.get('session_type', 'person'),
                    ),
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
