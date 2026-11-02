from __future__ import annotations

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
                return self.success(data={'uuid': workflow_uuid})
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
                    'categories': await self.ap.workflow_service.get_node_categories(),
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
            return self._read_response(request_context, data={'workflow': workflow})

        @self.route(
            '/<workflow_uuid>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.ap.workflow_service.update_workflow(request_context, workflow_uuid, await quart.request.json)
                return self.success()
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
                    data={'uuid': await self.ap.workflow_service.copy_workflow(request_context, workflow_uuid)}
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<workflow_uuid>/versions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            return self._read_response(
                request_context,
                data={'versions': await self.ap.workflow_service.get_versions(request_context, workflow_uuid)},
            )

        @self.route(
            '/<workflow_uuid>/rollback',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            payload = await quart.request.json
            try:
                await self.ap.workflow_service.rollback_to_version(
                    request_context, workflow_uuid, int(payload['version'])
                )
                return self.success()
            except (ValueError, KeyError, TypeError) as exc:
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
            '/<workflow_uuid>/stats',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            return self._read_response(
                request_context,
                data={'stats': await self.ap.workflow_service.get_workflow_stats(request_context, workflow_uuid)},
            )

        @self.route(
            '/<workflow_uuid>/run',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def _(workflow_uuid: str, request_context: RequestContext) -> str:
            payload = await quart.request.json
            try:
                return self.success(
                    data=await run_workflow(
                        self.ap,
                        request_context,
                        workflow_uuid,
                        payload.get('message'),
                        session_type=payload.get('session_type', 'person'),
                    )
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
