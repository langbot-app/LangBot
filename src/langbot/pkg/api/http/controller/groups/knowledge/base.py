import quart

from ....authz import Permission, has_permission
from ....context import RequestContext
from ... import group


@group.group_class('knowledge_base', '/api/v1/knowledge/bases')
class KnowledgeBaseRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def handle_knowledge_bases(request_context: RequestContext) -> quart.Response:
            knowledge_bases = await self.ap.knowledge_service.get_knowledge_bases(
                request_context,
                include_secret=has_permission(request_context, Permission.RESOURCE_MANAGE),
            )
            return self.success(data={'bases': knowledge_bases})

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def create_knowledge_base(request_context: RequestContext) -> quart.Response:
            json_data = await quart.request.json
            try:
                knowledge_base_uuid = await self.ap.knowledge_service.create_knowledge_base(
                    request_context,
                    json_data,
                )
            except ValueError as e:
                return self.http_status(400, -1, str(e))
            return self.success(data={'uuid': knowledge_base_uuid})

        @self.route(
            '/<knowledge_base_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_specific_knowledge_base(
            knowledge_base_uuid: str,
            request_context: RequestContext,
        ) -> quart.Response:
            knowledge_base = await self.ap.knowledge_service.get_knowledge_base(
                request_context,
                knowledge_base_uuid,
                include_secret=has_permission(request_context, Permission.RESOURCE_MANAGE),
            )
            if knowledge_base is None:
                return self.http_status(404, 'resource_not_found', 'knowledge base not found')
            return self.success(data={'base': knowledge_base})

        @self.route(
            '/<knowledge_base_uuid>',
            methods=['DELETE', 'PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def mutate_specific_knowledge_base(
            knowledge_base_uuid: str,
            request_context: RequestContext,
        ) -> quart.Response:
            if quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.knowledge_service.update_knowledge_base(
                    request_context,
                    knowledge_base_uuid,
                    json_data,
                )
                return self.success(data={'uuid': knowledge_base_uuid})
            await self.ap.knowledge_service.delete_knowledge_base(request_context, knowledge_base_uuid)
            return self.success({})

        @self.route(
            '/<knowledge_base_uuid>/files',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_knowledge_base_files(
            knowledge_base_uuid: str,
            request_context: RequestContext,
        ) -> str:
            files = await self.ap.knowledge_service.get_files_by_knowledge_base(
                request_context,
                knowledge_base_uuid,
            )
            return self.success(data={'files': files})

        @self.route(
            '/<knowledge_base_uuid>/files',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def add_knowledge_base_file(
            knowledge_base_uuid: str,
            request_context: RequestContext,
        ) -> str:
            json_data = await quart.request.json
            file_id = json_data.get('file_id')
            if not file_id:
                return self.http_status(400, -1, 'File ID is required')
            parser_plugin_id = json_data.get('parser_plugin_id')
            task_id = await self.ap.knowledge_service.store_file(
                request_context,
                knowledge_base_uuid,
                file_id,
                parser_plugin_id=parser_plugin_id,
            )
            return self.success({'task_id': task_id})

        @self.route(
            '/<knowledge_base_uuid>/files/<file_id>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def delete_specific_file_in_kb(
            file_id: str,
            knowledge_base_uuid: str,
            request_context: RequestContext,
        ) -> str:
            await self.ap.knowledge_service.delete_file(request_context, knowledge_base_uuid, file_id)
            return self.success({})

        @self.route(
            '/<knowledge_base_uuid>/retrieve',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def retrieve_knowledge_base(
            knowledge_base_uuid: str,
            request_context: RequestContext,
        ) -> str:
            json_data = await quart.request.json
            query = json_data.get('query')

            if not query or not query.strip():
                return self.http_status(400, -1, 'Query is required and cannot be empty')

            # Extract retrieval_settings to allow dynamic control over Knowledge Engine behavior (e.g. top_k, filters)
            retrieval_settings = json_data.get('retrieval_settings', {})
            results = await self.ap.knowledge_service.retrieve_knowledge_base(
                request_context,
                knowledge_base_uuid,
                query,
                retrieval_settings,
            )
            return self.success(data={'results': results})
