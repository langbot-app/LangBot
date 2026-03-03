import quart
from ... import group


@group.group_class('parsers', '/api/v1/knowledge/parsers')
class ParsersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def list_parsers() -> quart.Response:
            """List all available parsers from plugins.

            Optional query parameter `mime_type` to filter parsers by supported MIME type.
            """
            mime_type = quart.request.args.get('mime_type')
            parsers = await self.ap.knowledge_service.list_parsers(mime_type)
            return self.success(data={'parsers': parsers})
