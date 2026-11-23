"""User-confirmed migration only; deliberately not API-key/MCP accessible."""

import quart

from ... import group
from ....authz import Permission
from ....context import RequestContext
from ....service.pipeline_migration import PipelineMigrationService, MigrationError


@group.group_class('pipeline_migration', '/api/v1/pipelines/_/migration')
class PipelineMigrationRouterGroup(group.RouterGroup):
    async def initialize(self):
        self.service = PipelineMigrationService(self.ap)

        @self.route(
            '/preview', methods=['GET'], auth_type=group.AuthType.USER_TOKEN, permission=Permission.RESOURCE_VIEW
        )
        async def preview(request_context: RequestContext):
            try:
                return self.success(data=await self.service.preview(request_context))
            except MigrationError as exc:
                return self.http_status(exc.status_code, -1, exc.code)

        @self.route(
            '/execute', methods=['POST'], auth_type=group.AuthType.USER_TOKEN, permission=Permission.RESOURCE_MANAGE
        )
        async def execute(request_context: RequestContext):
            try:
                body = await quart.request.get_json(silent=True)
                return self.success(data=await self.service.execute(request_context, body))
            except MigrationError as exc:
                return self.http_status(exc.status_code, -1, exc.code)
