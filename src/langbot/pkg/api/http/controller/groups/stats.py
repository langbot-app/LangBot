from .. import group
from ...authz import Permission
from ...context import RequestContext


@group.group_class('stats', '/api/v1/stats')
class StatsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/basic',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.call_application('stats.basic', request_context, {}))
