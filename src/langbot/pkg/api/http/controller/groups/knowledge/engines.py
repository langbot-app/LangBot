import quart
from urllib.parse import unquote

from ....authz import Permission
from ....context import RequestContext
from ... import group


@group.group_class('knowledge_engines', '/api/v1/knowledge/engines')
class KnowledgeEnginesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def list_knowledge_engines(request_context: RequestContext) -> quart.Response:
            """List all available Knowledge Engines from plugins.

            Returns a list of Knowledge Engines with their capabilities and configuration schemas.
            This is used by the frontend to render the knowledge base creation wizard.
            """
            engines = await self.ap.knowledge_service.list_knowledge_engines(request_context)
            return self.success(data={'engines': engines})

        @self.route(
            '/<path:plugin_id>/creation-schema',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_engine_creation_schema(
            plugin_id: str,
            request_context: RequestContext,
        ) -> quart.Response:
            """Get creation settings schema for a specific Knowledge Engine.

            plugin_id is in 'author/name' format, captured via <path:> converter.
            """
            plugin_id = unquote(plugin_id)
            if '/' not in plugin_id:
                return self.http_status(400, -1, 'Invalid plugin_id format. Expected author/name.')
            schema = await self.ap.knowledge_service.get_engine_creation_schema(request_context, plugin_id)
            return self.success(data={'schema': schema})

        @self.route(
            '/<path:plugin_id>/retrieval-schema',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_engine_retrieval_schema(
            plugin_id: str,
            request_context: RequestContext,
        ) -> quart.Response:
            """Get retrieval settings schema for a specific Knowledge Engine.

            plugin_id is in 'author/name' format, captured via <path:> converter.
            """
            plugin_id = unquote(plugin_id)
            if '/' not in plugin_id:
                return self.http_status(400, -1, 'Invalid plugin_id format. Expected author/name.')
            schema = await self.ap.knowledge_service.get_engine_retrieval_schema(request_context, plugin_id)
            return self.success(data={'schema': schema})
