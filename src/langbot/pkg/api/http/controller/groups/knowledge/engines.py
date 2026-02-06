import quart
from urllib.parse import unquote
from ... import group


@group.group_class('rag_engines', '/api/v1/knowledge/engines')
class RAGEnginesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def list_rag_engines() -> quart.Response:
            """List all available RAG engines from plugins.

            Returns a list of RAG engines with their capabilities and configuration schemas.
            This is used by the frontend to render the knowledge base creation wizard.
            """
            engines = await self.ap.knowledge_service.list_rag_engines()
            return self.success(data={'engines': engines})

        @self.route('/<path:plugin_id>/creation-schema', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_engine_creation_schema(plugin_id: str) -> quart.Response:
            """Get creation settings schema for a specific RAG engine.

            plugin_id is in 'author/name' format, captured via <path:> converter.
            """
            plugin_id = unquote(plugin_id)
            schema = await self.ap.knowledge_service.get_engine_creation_schema(plugin_id)
            return self.success(data={'schema': schema})

        @self.route('/<path:plugin_id>/retrieval-schema', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_engine_retrieval_schema(plugin_id: str) -> quart.Response:
            """Get retrieval settings schema for a specific RAG engine.

            plugin_id is in 'author/name' format, captured via <path:> converter.
            """
            plugin_id = unquote(plugin_id)
            schema = await self.ap.knowledge_service.get_engine_retrieval_schema(plugin_id)
            return self.success(data={'schema': schema})
