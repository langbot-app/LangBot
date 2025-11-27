import quart
from ... import group


@group.group_class('external_knowledge_base', '/api/v1/knowledge/external-bases')
class ExternalKnowledgeBaseRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/retrievers', methods=['GET'])
        async def list_knowledge_retrievers() -> quart.Response:
            """List all available knowledge retrievers from plugins."""
            retrievers = await self.ap.plugin_connector.list_knowledge_retrievers()
            return self.success(data={'retrievers': retrievers})

        @self.route('', methods=['POST', 'GET'])
        async def handle_external_knowledge_bases() -> quart.Response:
            if quart.request.method == 'GET':
                external_kbs = await self.ap.external_kb_service.get_external_knowledge_bases()
                return self.success(data={'bases': external_kbs})

            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                kb_uuid = await self.ap.external_kb_service.create_external_knowledge_base(json_data)
                return self.success(data={'uuid': kb_uuid})

            return self.http_status(405, -1, 'Method not allowed')

        @self.route(
            '/<kb_uuid>',
            methods=['GET', 'DELETE', 'PUT'],
        )
        async def handle_specific_external_knowledge_base(kb_uuid: str) -> quart.Response:
            if quart.request.method == 'GET':
                external_kb = await self.ap.external_kb_service.get_external_knowledge_base(kb_uuid)

                if external_kb is None:
                    return self.http_status(404, -1, 'external knowledge base not found')

                return self.success(
                    data={
                        'base': external_kb,
                    }
                )

            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.external_kb_service.update_external_knowledge_base(kb_uuid, json_data)
                return self.success({})

            elif quart.request.method == 'DELETE':
                await self.ap.external_kb_service.delete_external_knowledge_base(kb_uuid)
                return self.success({})

        @self.route(
            '/<kb_uuid>/retrieve',
            methods=['POST'],
        )
        async def retrieve_external_knowledge_base(kb_uuid: str) -> str:
            json_data = await quart.request.json
            query = json_data.get('query')
            results = await self.ap.external_kb_service.retrieve_external_knowledge_base(kb_uuid, query)
            return self.success(data={'results': results})
