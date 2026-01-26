import quart
from ... import group


DEPRECATION_WARNING = (
    "This API is deprecated and will be removed in a future version. "
    "Please use /api/v1/knowledge/bases with rag_engine_plugin_id instead."
)


@group.group_class('external_knowledge_base', '/api/v1/knowledge/external-bases')
class ExternalKnowledgeBaseRouterGroup(group.RouterGroup):
    """
    DEPRECATED: External knowledge base routes.

    These endpoints are deprecated in favor of the unified knowledge base API
    at /api/v1/knowledge/bases. Use rag_engine_plugin_id to specify plugin-based
    RAG engines when creating knowledge bases.
    """

    def _add_deprecation_header(self, response: quart.Response) -> quart.Response:
        """Add deprecation warning header to response."""
        response.headers['X-Deprecated'] = 'true'
        response.headers['X-Deprecation-Notice'] = DEPRECATION_WARNING
        return response

    async def initialize(self) -> None:
        @self.route('/retrievers', methods=['GET'])
        async def list_knowledge_retrievers() -> quart.Response:
            """
            DEPRECATED: List all available knowledge retrievers from plugins.

            Use GET /api/v1/knowledge/engines instead.
            """
            retrievers = await self.ap.plugin_connector.list_knowledge_retrievers()
            response = self.success(data={
                'retrievers': retrievers,
                '_deprecation_warning': DEPRECATION_WARNING,
            })
            return self._add_deprecation_header(response)

        @self.route('', methods=['POST', 'GET'])
        async def handle_external_knowledge_bases() -> quart.Response:
            """
            DEPRECATED: Handle external knowledge bases.

            Use /api/v1/knowledge/bases instead.
            """
            if quart.request.method == 'GET':
                external_kbs = await self.ap.external_kb_service.get_external_knowledge_bases()
                response = self.success(data={
                    'bases': external_kbs,
                    '_deprecation_warning': DEPRECATION_WARNING,
                })
                return self._add_deprecation_header(response)

            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                kb_uuid = await self.ap.external_kb_service.create_external_knowledge_base(json_data)
                response = self.success(data={
                    'uuid': kb_uuid,
                    '_deprecation_warning': DEPRECATION_WARNING,
                })
                return self._add_deprecation_header(response)

            return self.http_status(405, -1, 'Method not allowed')

        @self.route(
            '/<kb_uuid>',
            methods=['GET', 'DELETE', 'PUT'],
        )
        async def handle_specific_external_knowledge_base(kb_uuid: str) -> quart.Response:
            """
            DEPRECATED: Handle specific external knowledge base.

            Use /api/v1/knowledge/bases/<uuid> instead.
            """
            if quart.request.method == 'GET':
                external_kb = await self.ap.external_kb_service.get_external_knowledge_base(kb_uuid)

                if external_kb is None:
                    return self.http_status(404, -1, 'external knowledge base not found')

                response = self.success(
                    data={
                        'base': external_kb,
                        '_deprecation_warning': DEPRECATION_WARNING,
                    }
                )
                return self._add_deprecation_header(response)

            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.external_kb_service.update_external_knowledge_base(kb_uuid, json_data)
                response = self.success({'_deprecation_warning': DEPRECATION_WARNING})
                return self._add_deprecation_header(response)

            elif quart.request.method == 'DELETE':
                await self.ap.external_kb_service.delete_external_knowledge_base(kb_uuid)
                response = self.success({'_deprecation_warning': DEPRECATION_WARNING})
                return self._add_deprecation_header(response)

        @self.route(
            '/<kb_uuid>/retrieve',
            methods=['POST'],
        )
        async def retrieve_external_knowledge_base(kb_uuid: str) -> str:
            """
            DEPRECATED: Retrieve from external knowledge base.

            Use POST /api/v1/knowledge/bases/<uuid>/retrieve instead.
            """
            json_data = await quart.request.json
            query = json_data.get('query')
            results = await self.ap.external_kb_service.retrieve_external_knowledge_base(kb_uuid, query)
            response = self.success(data={
                'results': results,
                '_deprecation_warning': DEPRECATION_WARNING,
            })
            return self._add_deprecation_header(response)
