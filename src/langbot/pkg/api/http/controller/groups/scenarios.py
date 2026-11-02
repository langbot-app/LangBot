import quart

from ...authz import Permission
from ...context import RequestContext
from .. import group


@group.group_class('scenarios', '/api/v1/scenarios')
class ScenariosRouterGroup(group.RouterGroup):
    async def initialize(self):
        from ...service.scenario import ScenarioPackService

        service = ScenarioPackService(self.ap)

        @self.route(
            '', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY, permission=Permission.RESOURCE_MANAGE
        )
        async def list_imports(request_context: RequestContext):
            return self.success(data={'imports': await service.list_imports(request_context)})

        @self.route(
            '/export/<bot_uuid>',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def export(bot_uuid: str, request_context: RequestContext):
            body = await quart.request.get_json()
            try:
                return self.success(data=await service.export(request_context, bot_uuid, body))
            except ValueError as exc:
                return self.http_status(400, 'invalid_scenario', str(exc))

        @self.route(
            '/preview',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def preview(request_context: RequestContext):
            try:
                return self.success(data=await service.preview(request_context, await quart.request.get_json()))
            except ValueError as exc:
                return self.http_status(400, 'invalid_scenario', str(exc))

        @self.route(
            '/import',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def import_package(request_context: RequestContext):
            body = await quart.request.get_json()
            if not isinstance(body, dict):
                return self.http_status(400, 'invalid_scenario', 'Scenario request must be an object')
            try:
                return self.success(
                    data=await service.import_package(
                        request_context,
                        body.get('package'),
                        body.get('request_id', ''),
                    )
                )
            except ValueError as exc:
                return self.http_status(400, 'invalid_scenario', str(exc))

        @self.route(
            '/<import_id>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def status(import_id: str, request_context: RequestContext):
            return self.success(data=await service.status(request_context, import_id))
