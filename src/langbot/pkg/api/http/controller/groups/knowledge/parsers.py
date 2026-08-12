import quart

from ....authz import Permission
from ....context import RequestContext
from ... import group


@group.group_class('parsers', '/api/v1/knowledge/parsers')
class ParsersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def list_parsers(request_context: RequestContext) -> quart.Response:
            """List all available parsers from plugins.

            Optional query parameter `mime_type` to filter parsers by supported MIME type.
            """
            mime_type = quart.request.args.get('mime_type')
            parsers = await self.ap.knowledge_service.list_parsers(request_context, mime_type)
            return self.success(data={'parsers': parsers})
