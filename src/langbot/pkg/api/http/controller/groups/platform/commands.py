from ....authz import Permission
from ....context import RequestContext
from ... import group


@group.group_class('platform_commands', '/api/v1/bots')
class PlatformCommandsRouterGroup(group.RouterGroup):
    async def initialize(self):
        @self.route(
            '/<bot_uuid>/platform-commands/sync',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def sync(bot_uuid: str, request_context: RequestContext):
            return self.success(data=await self.ap.bot_service.sync_platform_commands(request_context, bot_uuid))
